from logging import Logger, getLogger
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    Optional,
    Type,
    Tuple,
    TypeVar,
    Union,
)

import ipywidgets as widgets
import traitlets
import dataclasses
import inspect

from .types import TraitViewFactoryType
from .widgets import ModelViewWidget

default_logger = getLogger(__name__)


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


T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class ViewFactoryContext:
    _factory: "ViewFactory"
    _visited_model_classes: FrozenSet[Type[traitlets.HasTraits]] = frozenset()
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    path: Tuple[str, ...] = ()

    @property
    def name(self) -> Union[str, None]:
        try:
            return self.path[-1]
        except IndexError:
            return None

    @property
    def logger(self) -> Logger:
        return self._factory.logger

    @property
    def display_name(self) -> Union[str, None]:
        if self.name is None:
            return None
        return self.name.replace("_", " ").title()

    def create_widgets_for_model_cls(
        self, model_cls: Type[traitlets.HasTraits]
    ) -> Dict[str, widgets.Widget]:
        return self._factory.create_widgets_for_model_cls(model_cls, self)

    def create_trait_view(self, trait: traitlets.TraitType) -> widgets.Widget:
        return self._factory.create_trait_view(trait, self)

    def enter_model_cls(
        self, model_cls: Type[traitlets.HasTraits]
    ) -> "ViewFactoryContext":
        if model_cls in self._visited_model_classes:
            raise ValueError(f"Already visited {model_cls!r}")

        return dataclasses.replace(
            self, _visited_model_classes=(self._visited_model_classes | {model_cls})
        )

    def follow_trait(
        self, name: str, trait: traitlets.TraitType
    ) -> "ViewFactoryContext":
        return dataclasses.replace(
            self,
            path=self.path + (name,),
            metadata={**trait.metadata, **self.metadata.get(name, {})},
        )

    def resolve(self, name_or_cls: Union[str, Type[T]]) -> Type[T]:
        return self._factory.resolve(name_or_cls)


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


class ViewFactory:
    def __init__(
        self,
        logger: Logger = default_logger,
        namespace: Dict[str, Any] = None,
        filter_trait: FilterType = None,
        metadata: Dict[str, Any] = None,
    ):
        self.logger = logger
        self._namespace = namespace or {}
        self._visited = set()
        self._root_ctx = ViewFactoryContext(self, metadata=metadata or {})
        self._filter_trait = filter_trait

    def can_visit_trait(
        self, model_cls: Type[traitlets.HasTraits], trait, ctx: ViewFactoryContext
    ) -> bool:
        """Test to determine whether to visit a trait

        :param model_cls: model class object
        :param trait: trait instance
        :param ctx: factory context
        :return:
        """
        # Skip hidden traits
        if ctx.metadata.get("hidden"):
            return False

        if callable(self._filter_trait):
            return self._filter_trait(model_cls, trait, ctx)
        return True

    def create_root_view(
        self, model: traitlets.HasTraits, **kwargs: Any
    ) -> ModelViewWidget:
        """Create the root view for a model

        :param model: HasTraits instance
        :param kwargs: model widget keyword arguments
        :return:
        """
        model_view_cls = ModelViewWidget.specialise_for_cls(type(model))

        return model_view_cls(ctx=self._root_ctx, value=model, **kwargs)

    def create_trait_view(
        self,
        trait: traitlets.TraitType,
        ctx: ViewFactoryContext,
    ) -> widgets.Widget:
        """Return the best view constructor for a given trait

        :param trait: trait instance
        :param ctx: factory context
        :return:
        """
        factory = get_trait_view_variant_factory(type(trait))

        # Remove 'variant' field from metadata
        variant = ctx.metadata.get("variant", None)

        # Allow library to propose variants
        supported_variants = list(factory(trait, ctx))
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

        # Traitlets cannot receive additional arguments
        # Although the end widget should resolve to a `HasTraits` instance,
        # permit deferred constructors to be used
        if issubclass(cls, traitlets.HasTraits):
            trait_names = set(cls.class_trait_names())
        elif hasattr(cls, "valid_arg_names"):
            trait_names = set(cls.valid_arg_names())
        else:
            signature = inspect.signature(cls)
            trait_names = signature.parameters.keys()

        constructor_kwargs = {
            k: v for k, v in constructor_kwargs.items() if k in trait_names
        }

        # Set widget disabled according to trait by default
        kwargs = {"disabled": trait.read_only, **constructor_kwargs}

        return cls(**kwargs)

    def create_widgets_for_model_cls(
        self, model_cls: Type[traitlets.HasTraits], ctx: ViewFactoryContext
    ) -> Dict[str, widgets.Widget]:
        """Return a mapping from name to widget for a given model class

        :param model_cls: model class object
        :param ctx: factory context
        :return:
        """
        ctx = ctx.enter_model_cls(model_cls)

        model_widgets = {}
        for name, widget in self.iter_widgets_for_model(model_cls, ctx):
            self.logger.info(f"Created widget {widget} for trait {name!r}")
            model_widgets[name] = widget

        return model_widgets

    def iter_traits(
        self, model_cls: Type[traitlets.HasTraits]
    ) -> Iterator[Tuple[str, traitlets.TraitType]]:
        """Iterate over the name, trait pairs of the model class

        :param model_cls: model class object
        :return:
        """
        for c in reversed(model_cls.__mro__):
            for k, v in vars(c).items():
                if isinstance(v, traitlets.TraitType):
                    yield k, v

    def iter_widgets_for_model(
        self, model_cls: Type[traitlets.HasTraits], ctx: ViewFactoryContext
    ) -> Iterator[Tuple[str, widgets.Widget]]:
        """Yield (name, widget) pairs corresponding to the traits defined by a model class

        :param model_cls: model class object
        :param ctx: factory context
        :return:
        """
        for name, trait in self.iter_traits(model_cls):
            trait_ctx = ctx.follow_trait(name, trait)

            if not self.can_visit_trait(model_cls, trait, trait_ctx):
                continue

            # Inject description only if not set by trait tag or metadata
            if trait_ctx.metadata.get("description") is None:
                trait_ctx = dataclasses.replace(
                    trait_ctx,
                    metadata={
                        **trait_ctx.metadata,
                        "description": trait_ctx.display_name,
                    },
                )

            try:
                widget = self.create_trait_view(trait, trait_ctx)

            except:
                ctx.logger.exception(
                    f"Unable to render trait {name!r} ({type(trait).__qualname__})"
                )
                continue

            yield name, widget

    def resolve(self, name_or_cls: Union[str, Type[T]]) -> Type[T]:
        """Resolve the reference to a class

        :param name_or_cls: name of class, or class itself
        :return:
        """
        if isinstance(name_or_cls, str):
            return self._namespace[name_or_cls]
        return name_or_cls
