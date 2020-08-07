import math
from logging import Logger, getLogger
from typing import Any, Callable, Dict, Iterator, Optional, Type, Tuple, Union

import ipywidgets as widgets
import traitlets

from .widgets import ModelViewWidget

default_logger = getLogger(__name__)


class ViewFactoryContext:
    def __init__(self, factory: "ViewFactory", path: Tuple[str, ...]):
        self._factory = factory
        self.path = path
        self.logger = factory.logger

    @property
    def name(self) -> Union[str, None]:
        if self.path:
            return self.path[-1]
        return None

    @property
    def display_name(self) -> Union[str, None]:
        if self.name is None:
            return None
        return self.name.replace("_", " ").title()

    def create_widgets_for_model_cls(self, model_cls: Type[traitlets.HasTraits]):
        return self._factory.create_widgets_for_model_cls(model_cls, self)

    def create_trait_view(self, trait: traitlets.TraitType, metadata: Dict[str, Any]):
        return self._factory.create_trait_view(trait, metadata, self)

    def resolve(self, name_or_cls: Union[type, str]) -> type:
        return self._factory.resolve(name_or_cls)

    def follow(self, name: str) -> "ViewFactoryContext":
        return type(self)(self._factory, self.path + (name,))


FilterType = Callable[
    [Type[traitlets.HasTraits], Tuple[str, ...], traitlets.TraitType], bool
]


TransformerType = Callable[
    [
        Type[traitlets.HasTraits],
        traitlets.TraitType,
        widgets.Widget,
        ViewFactoryContext,
    ],
    Optional[widgets.Widget],
]


VariantIterator = Iterator[Tuple[Type[widgets.Widget], Dict[str, Any]]]
TraitViewFactoryType = Callable[
    [traitlets.TraitType, Dict[str, Any], ViewFactoryContext], VariantIterator
]
_trait_view_variant_factories: Dict[
    Type[traitlets.TraitType], TraitViewFactoryType
] = {}


class ViewFactory:
    def __init__(
        self,
        logger: Logger = default_logger,
        filter_trait: FilterType = None,
        transform_trait: TransformerType = None,
        namespace: Dict[str, Any] = None,
    ):
        self.logger = logger

        self._filter_trait = filter_trait
        self._transform_trait = transform_trait
        self._namespace = namespace or {}
        self._visited = set()

    def resolve(self, name_or_cls: Union[str, type]) -> type:
        if isinstance(name_or_cls, str):
            return self._namespace[name_or_cls]
        return name_or_cls

    def create_root_view(self, model: traitlets.HasTraits, metadata: Dict[str, Any]):
        model_view_cls = ModelViewWidget.specialise_for_cls(type(model))
        return model_view_cls(ctx=ViewFactoryContext(self, ()), value=model, **metadata)

    def create_trait_view(
        self,
        trait: traitlets.TraitType,
        metadata: Dict[str, Any],
        ctx: ViewFactoryContext = None,
    ) -> widgets.Widget:
        """Return the best view constructor for a given trait

        :param trait:
        :param metadata:
        :param ctx:
        :return:
        """
        if ctx is None:
            ctx = ViewFactoryContext(self, ())

        factory = get_trait_view_variant_factory(type(trait))

        # Allow model or caller to set view metadata
        view_metadata = {**trait.metadata, **metadata}

        # Remove 'variant' field from metadata
        variant = view_metadata.pop("variant", None)

        # Allow library to propose variants
        supported_variants = list(factory(trait, view_metadata, ctx))
        if not supported_variants:
            raise ValueError(f"No variant found for {trait}")

        # Find variant
        if variant is None:
            cls, constructor_kwargs = supported_variants[-1]
        else:
            # Find the widget class for this variant, if possible
            cls, constructor_kwargs = request_constructor_for_variant(
                supported_variants, variant
            )

        # Traitlets cannot receive additional arguments.
        # Use factories should handle these themselves
        if issubclass(cls, traitlets.HasTraits):
            trait_names = set(cls.class_trait_names())
            constructor_kwargs = {
                k: v for k, v in constructor_kwargs.items() if k in trait_names
            }

        # Set widget disabled according to trait by default
        kwargs = {"disabled": trait.read_only, **constructor_kwargs}

        return cls(**kwargs)

    def create_widgets_for_model_cls(
        self, model_cls: Type[traitlets.HasTraits], ctx: ViewFactoryContext
    ):
        if model_cls in self._visited:
            raise ValueError(f"Already visited {model_cls!r}")

        self._visited.add(model_cls)

        model_widgets = {}
        for name, trait in model_cls.class_traits().items():
            trait_ctx = ctx.follow(name)

            if not self.filter_trait(model_cls, trait, trait_ctx):
                continue

            # Set description only if not set by tag
            # Required because metadata field takes priority over tag metadata
            description = trait.metadata.get(
                "description", trait_ctx.display_name
            )

            try:
                widget = self.create_trait_view(
                    trait, {"description": description}, trait_ctx
                )
            except:
                self.logger.exception(
                    f"Unable to render trait {name!r} ({type(trait).__qualname__})"
                )
                continue

            # Call user visitor and allow it to replace the widget
            widget = self.transform_trait(model_cls, trait, widget, trait_ctx)

            self.logger.info(f"Created widget {widget} for trait {name!r}")
            model_widgets[name] = widget
        return model_widgets

    def filter_trait(
        self, model_cls: Type[traitlets.HasTraits], trait, ctx: ViewFactoryContext
    ):
        if self._filter_trait is None:
            return True

        try:
            return self._filter_trait(model_cls, ctx.path, trait)

        except ValueError:
            self.logger.info(
                f"Unable to follow trait {'.'.join(ctx.path)} ({type(trait).__qualname__})"
            )
            return False

    def transform_trait(
        self,
        model_cls: Type[traitlets.HasTraits],
        trait: traitlets.TraitType,
        widget: widgets.Widget,
        ctx: ViewFactoryContext,
    ):
        if self._transform_trait is None:
            return widget

        return self._transform_trait(model_cls, trait, widget, ctx) or widget


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
        default_logger.debug(
            f"Unable to find variant {variant} in {variant_kwarg_pairs}"
        )

    return cls, kwargs


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


@trait_view_variants(traitlets.Instance)
def _instance_view_factory(
    trait: traitlets.Instance, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    model_cls = ctx.resolve(trait.klass)

    if not issubclass(model_cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    model_view_cls = ModelViewWidget.specialise_for_cls(model_cls)
    yield model_view_cls, {"ctx": ctx, **metadata}


@trait_view_variants(
    traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName
)
def _unicode_view_factory(
    trait: traitlets.TraitType, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.Text, metadata


@trait_view_variants(traitlets.Enum)
def _enum_view_factory(
    trait: traitlets.Enum, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    params = {"options": sorted(trait.values), **metadata}

    yield widgets.SelectionSlider, params
    yield widgets.Dropdown, params


@trait_view_variants(traitlets.Bool)
def _bool_view_factory(
    trait: traitlets.Bool, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.Checkbox, {"indent": True, **metadata}


@trait_view_variants(traitlets.Float)
def _float_view_factory(
    trait: traitlets.Float, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    # Unbounded variant
    yield widgets.FloatText, metadata

    # Build UI params store
    params = {"min": trait.min, "max": trait.max, **metadata}

    # Require min to be set
    if params["min"] is None or not math.isfinite(params["min"]):
        return

    # Require max to be set
    if params["max"] is None or not math.isfinite(params["max"]):
        return

    # Bounded variants:
    yield widgets.BoundedFloatText, params
    yield widgets.FloatSlider, params

    # Logarithmic bounded variant
    if params.get("base") is not None:
        yield widgets.FloatLogSlider, params


@trait_view_variants(traitlets.Integer)
def _integer_view_factory(
    trait: traitlets.Integer, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.IntText, metadata

    params = {"min": trait.min, "max": trait.max, **metadata}
    if params["min"] is None or params["max"] is None:
        return

    yield widgets.BoundedIntText, params
    yield widgets.IntSlider, params
