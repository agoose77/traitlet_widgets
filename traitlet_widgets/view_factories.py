import dataclasses
import math
import types
from logging import Logger, getLogger
from typing import Any, Callable, Dict, Iterator, Optional, Type, Tuple, Union

import ipywidgets as widgets
import traitlets

from .widgets import ModelViewWidget


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
TraitViewFactoryType = Callable[
    [traitlets.TraitType, ViewContext, Dict[str, Any]], VariantIterator
]
_trait_view_variant_factories: Dict[
    Type[traitlets.TraitType], TraitViewFactoryType
] = {}


def request_constructor_for_variant(
    variant_kwarg_pairs, variant: Type[widgets.Widget] = None
) -> Tuple[Any, Dict[str, Any]]:
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


def create_best_widget(
    ctx: ViewContext, trait: traitlets.TraitType, variant, metadata: Dict[str, Any]
):
    """Return the best view constructor for a given trait

    :param ctx:
    :param trait:
    :param variant:
    :param metadata:
    :return:
    """
    factory = get_trait_view_variant_factory(type(trait))

    # Allow model or caller to set view metadata
    view_metadata = {**trait.metadata, **metadata}

    # Allow library to propose variants
    supported_variants = list(factory(trait, ctx, view_metadata))
    if not supported_variants:
        raise ValueError(f"No variant found for {trait}")

    # Find variant
    variant = variant or trait.metadata.get("variant")
    if variant is None:
        cls, kwargs = supported_variants[-1]
    else:
        # Find the widget class for this variant, if possible
        cls, kwargs = request_constructor_for_variant(supported_variants, variant)

    # Traitlets cannot receive additional arguments.
    # Use factories should handle these themselves
    if issubclass(cls, traitlets.HasTraits):
        trait_names = set(cls.class_trait_names())
        kwargs = {k: v for k, v in kwargs.items() if k in trait_names}

    return cls(**kwargs)


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
    :param metadata: view metadata
    :return:
    """
    widget = create_best_widget(ctx, trait, variant, metadata or {})

    # Set any useful values using metadata
    for key, value in trait.metadata.items():
        if hasattr(widget, key):
            logger.debug("Setting {trait} metadata {key} = {value!r} on {widget}")
            setattr(widget, key, value)

    # Set read/write status from trait
    widget.disabled = trait.read_only
    return widget


def get_trait_view_variant_factory(
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


def create_widgets_for_model_cls(
    model_cls: Type[traitlets.HasTraits], ctx: ViewContext
):
    if model_cls in ctx.visited:
        raise ValueError(f"Already visited {model_cls!r}")

    ctx.visited.add(model_cls)

    model_widgets = {}
    for name, trait in model_cls.class_traits().items():
        # Support externally registered widgets
        try:
            derived_ctx = ctx.follow_trait(model_cls, name)
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
        widget = ctx.transform_widget(model_cls, name, trait, widget) or widget

        # Set default widget description
        if not widget.description:
            widget.description = name.replace("_", " ").title()

        ctx.logger.info(f"Created widget {widget} for trait {name!r}")
        model_widgets[name] = widget
    return model_widgets


def has_traits_view_factory(
    model_cls: Type[traitlets.HasTraits], ctx: ViewContext
) -> ModelViewWidget:
    model_widgets = create_widgets_for_model_cls(model_cls, ctx)
    model_widget_class = ModelViewWidget.specialise_for_cls(model_cls)
    return model_widget_class(model_widgets, ctx.logger)


@trait_view_variants(traitlets.Instance)
def _instance_view_factory(
    trait: traitlets.Instance, ctx, metadata: Dict[str, Any]
) -> VariantIterator:
    model_cls = trait.klass
    if isinstance(model_cls, str):
        model_cls = ctx.namespace[model_cls]

    if not issubclass(model_cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    model_view_cls = ModelViewWidget.specialise_for_cls(model_cls)
    yield model_view_cls, {"ctx": ctx, **metadata}


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
    yield widgets.IntText, metadata

    params = {"min": trait.min, "max": trait.max, **metadata}
    if params["min"] is None or params["max"] is None:
        return

    yield widgets.BoundedIntText, params
    yield widgets.IntSlider, params
