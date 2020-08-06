import dataclasses
import math
import types
from logging import Logger, getLogger
from typing import Any, Callable, Dict, Iterator, Optional, Type, Tuple, Union

import ipywidgets as widgets
import traitlets

from .widgets import HasTraitsViewWidget

logger = getLogger(__name__)


CanFollowTraitType = Callable[[traitlets.HasTraits, Tuple[str, ...]], bool]


@dataclasses.dataclass
class ViewContext:
    namespace: Dict[str, Any]
    transformer: "TransformerType"
    visited: set
    logger: Logger
    path: Tuple[str, ...]
    can_follow_trait: CanFollowTraitType

    def resolve_name(self, name: str) -> Tuple[str, ...]:
        return self.path + (name,)

    def follow_trait(self, model: traitlets.HasTraits, name: str) -> "ViewContext":
        new_path = self.resolve_name(name)

        if callable(self.can_follow_trait) and not self.can_follow_trait(
            model, new_path
        ):
            raise ValueError

        return dataclasses.replace(self, path=new_path)

    def transform_widget(
        self,
        model: traitlets.HasTraits,
        name: str,
        trait: traitlets.TraitType,
        widget: widgets.Widget,
    ) -> Optional[widgets.Widget]:
        """Call the user defined visitor with a given model field

        :param model:
        :param name:
        :param trait:
        :param widget:
        :return:
        """
        if callable(self.transformer):
            return self.transformer(self, model, name, trait, widget)


TransformerType = Callable[
    [ViewContext, traitlets.HasTraits, str, traitlets.TraitType, widgets.Widget],
    Optional[widgets.Widget],
]

VariantIterator = Iterator[Tuple[Type[widgets.Widget], Dict[str, Any]]]
TraitViewFactoryType = Callable[[traitlets.TraitType, ViewContext], VariantIterator]
_trait_view_variant_factories: Dict[
    Type[traitlets.TraitType], TraitViewFactoryType
] = {}


def request_constructor_for_variant(
    variant_kwarg_pairs, variant: Type[widgets.Widget] = None
):
    """Return best widget constructor from a series of candidates. Attempt to satisfy variant.

    :param variant_kwarg_pairs: sequence of (widget_cls, kwarg) pairs
    :param variant: optional requested variant.
    :return:
    """
    assert variant_kwarg_pairs

    for cls, kwargs in variant_kwarg_pairs:
        if cls is variant:
            break
    else:
        logger.debug(f"Unable to find variant {variant} in {variant_kwarg_pairs}")

    return cls, kwargs


def get_widget_constructor(ctx, trait, variant, metadata):
    factory = _get_trait_view_variant_factory(type(trait))

    # Allow library to propose variants
    supported_variants = list(factory(trait, ctx, {**trait.metadata, **metadata}))
    if not supported_variants:
        raise ValueError(f"No variant found for {trait}")

    # Find variant
    variant = variant or trait.metadata.get("variant")
    if variant is None:
        cls, kwargs = supported_variants[-1]
    else:
        # Find the widget class for this variant, if possible
        cls, kwargs = request_constructor_for_variant(supported_variants, variant)

    valid_attributes = {k: v for k, v in kwargs.items() if hasattr(cls, k)}
    return cls, valid_attributes


def create_trait_view(
    ctx: ViewContext,
    trait: traitlets.TraitType,
    variant: Type[widgets.Widget] = None,
    metadata: Dict[str, Any] = None,
) -> widgets.Widget:
    """Create a view for a trait

    :param ctx: render context
    :param trait: traitlet instance
    :param variant: optionally request a widget variant
    :return:
    """
    cls, kwargs = get_widget_constructor(ctx, trait, variant, metadata)

    # Create widget
    widget = cls(**kwargs)

    # Set any useful values using metadata
    for key, value in trait.metadata.items():
        if hasattr(widget, key):
            logger.debug("Setting {trait} metadata {key} = {value!r} on {widget}")
            setattr(widget, key, value)

    # Set read/write status from trait
    widget.disabled = trait.read_only
    return widget


def _get_trait_view_variant_factory(
    trait_type: Type[traitlets.TraitType],
) -> TraitViewFactoryType:
    """Get a view factory for a given trait class

    :param trait_type: trait class
    :return:
    """
    for cls in trait_type.__mro__:
        try:
            return _trait_view_variant_factories[cls]
        except KeyError:
            continue
    raise ValueError(f"Couldn't find factory for {trait_type}")


def register_trait_view_variant_factory(
    *trait_types: Type[traitlets.TraitType], variant_factory: TraitViewFactoryType
):
    """Register a view factory for a given traitlet type(s)

    :param trait_types: trait class(es) to register
    :param variant_factory: view factory for trait class(es)
    :return:
    """
    for trait_type in trait_types:
        _trait_view_variant_factories[trait_type] = variant_factory


def unregister_trait_view_variant_factory(*trait_types: Type[traitlets.TraitType]):
    """Unregister a view factory for a given traitlet type(s)

    :param trait_types: trait class(es) to unregister
    :return:
    """
    for trait_type in trait_types:
        del _trait_view_variant_factories[trait_type]


def trait_view_variants(*trait_types: Type[traitlets.TraitType]):
    """Decorator for  registering view factory functions

    :param trait_types: trait class(es) to register
    :return:
    """

    def wrapper(factory):
        register_trait_view_variant_factory(*trait_types, variant_factory=factory)
        return factory

    return wrapper


def create_has_traits_widgets(has_traits: Type[traitlets.HasTraits], ctx: ViewContext):
    if has_traits in ctx.visited:
        raise ValueError(f"Already visited {has_traits!r}")

    ctx.visited.add(has_traits)

    model_widgets = {}
    for name, trait in has_traits.class_traits().items():
        # Support externally registered widgets
        try:
            derived_ctx = ctx.follow_trait(has_traits, name)
        except ValueError:
            ctx.logger.info(
                f"Unable to follow trait {name!r} ({type(trait).__qualname__})"
            )
            continue

        try:
            widget = create_trait_view(derived_ctx, trait)
        except:
            ctx.logger.exception(
                f"Unable to render trait {name!r} ({type(trait).__qualname__})"
            )
            continue

        # Call user visitor and allow it to replace the widget
        widget = ctx.transform_widget(has_traits, name, trait, widget) or widget

        # Set default widget description
        if not widget.description:
            widget.description = name.replace("_", " ").title()

        ctx.logger.info(f"Created widget {widget} for trait {name!r}")
        model_widgets[name] = widget
    return model_widgets


def has_traits_view_factory(has_traits: Type[traitlets.HasTraits], ctx: ViewContext):
    model_widgets = create_has_traits_widgets(has_traits, ctx)
    model_widget_class = HasTraitsViewWidget.specialise_for_cls(has_traits)
    return model_widget_class(model_widgets, ctx.logger)


@trait_view_variants(traitlets.Instance)
def _instance_view_factory(
    trait: traitlets.Instance, ctx, metadata: Dict[str, Any]
) -> VariantIterator:
    cls = trait.klass
    if isinstance(cls, str):
        cls = ctx.namespace[cls]

    if not issubclass(cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    yield has_traits_view_factory, {"has_traits": cls, "ctx": ctx}


@trait_view_variants(
    traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName
)
def _unicode_view_factory(
    trait: traitlets.TraitType, ctx: ViewContext, metadata: Dict[str, Any]
) -> VariantIterator:
    yield widgets.Text, metadata


@trait_view_variants(traitlets.Enum)
def _enum_view_factory(
    trait: traitlets.Enum, ctx: ViewContext, metadata: Dict[str, Any]
) -> VariantIterator:
    params = {"options": sorted(trait.values), **metadata}

    yield widgets.SelectionSlider, params
    yield widgets.Dropdown, params


@trait_view_variants(traitlets.Bool)
def _bool_view_factory(
    trait: traitlets.Bool, ctx: ViewContext, metadata: Dict[str, Any]
) -> VariantIterator:
    yield widgets.Checkbox, {"indent": True, **metadata}


@trait_view_variants(traitlets.Float)
def _float_view_factory(
    trait: traitlets.Float, ctx: ViewContext, metadata: Dict[str, Any]
) -> VariantIterator:
    # Unbounded variant
    yield widgets.FloatText, metadata

    # Build UI params store
    params = {"min": trait.min, "max": trait.max, **metadata}

    # Require min to be set
    if params["min"] is not None and math.isfinite(params["min"]):
        return

    # Require max to be set
    if params["max"] is not None and math.isfinite(params["max"]):
        return

    # Bounded variants:
    yield widgets.BoundedFloatText, params
    yield widgets.FloatSlider, params

    # Logarithmic bounded variant
    if params.get("base") is not None:
        yield widgets.FloatLogSlider, params


@trait_view_variants(traitlets.Integer)
def _integer_view_factory(
    trait: traitlets.Integer, ctx: ViewContext, metadata: Dict[str, Any]
) -> VariantIterator:
    yield widgets.IntText, {}

    params = {"min": trait.min, "max": trait.max, **metadata}
    if params["min"] is None or params["max"] is None:
        return

    yield widgets.BoundedIntText, params
    yield widgets.IntSlider, params
