import math
import dataclasses
from logging import Logger, getLogger
from typing import Callable, Type, Dict, Any, Union, Set, Tuple

import ipywidgets as widgets
import traitlets
from inspect import signature
from functools import wraps

ObserverType = Callable[..., None]
root_logger = getLogger(__name__)


def model_observer(
    model: traitlets.HasTraits, func: ObserverType = None
) -> ObserverType:
    """Observe changes to a model and pass them to the correspondingly named parameters of the function

    :param model: observable (`.observe`) model
    :param func: function to invoke with updates. Leave `None` if using as a decorator
    :return:
    """
    if not isinstance(model, traitlets.HasTraits):
        raise ValueError("Expected `traitlets.HasTraits` instance as first argument.")

    def wrapper(decorated):
        params = signature(decorated).parameters

        for name in params:
            if name not in model.trait_names():
                raise ValueError(
                    f"Observer parameter {name!r} is not defined "
                    f"for model with traits {model.trait_names()}"
                )

        def update_func(change):
            state = {n: getattr(model, n) for n in params}
            decorated(**state)

        for name in params:
            model.observe(update_func, name)
        return decorated

    if func is None:
        return wrapper

    return wrapper(func)


CanFollowTraitType = Callable[[traitlets.HasTraits, Tuple[str, ...]], bool]


def default_can_follow_trait(model, path):
    return True


def is_public_trait(model, path):
    return not path[-1].startswith("_")


def is_own_trait(model, path):
    return path[-1] in model.class_own_traits()


@dataclasses.dataclass
class RenderContext:
    namespace: Dict[str, Any]
    format_label: Callable[[str], str]
    visited: set
    logger: Logger
    path: Tuple[str, ...]
    can_follow_trait: CanFollowTraitType

    def follow_trait(self, model: traitlets.HasTraits, name: str) -> "RenderContext":
        new_path = self.path + (name,)
        if callable(self.can_follow_trait) and not self.can_follow_trait(
            model, new_path
        ):
            raise ValueError

        return dataclasses.replace(self, path=new_path)


def logical_and(first, *functions):
    """Logically combine functions with the same signature using AND"""
    if not functions:
        return first

    right = logical_and(*functions)

    @wraps(first)
    def left(*args, **kwargs):
        return first(*args, **kwargs) and right(*args, **kwargs)

    return left


def model_view(
    model: traitlets.HasTraits,
    format_label: Callable[[str], str] = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = root_logger,
    hide_private_traits: bool = True,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
) -> "_ModelWidget":
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param format_label: function to format labels
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param hide_private_traits: show/hide traits prefixed with "_"
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """
    if hide_private_traits:
        can_follow_trait = logical_and(can_follow_trait, is_public_trait)

    ctx = RenderContext(
        format_label=format_label,
        namespace=namespace or {},
        logger=logger,
        visited=set(),
        path=(),
        can_follow_trait=can_follow_trait,
    )
    view = _type_has_traits_view_factory(type(model), ctx)
    view.value = model
    return view


def model_view_for(
    model_cls: Type[traitlets.HasTraits],
    format_label: Callable[[str], str] = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = root_logger,
    hide_private_traits: bool = True,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
) -> "_ModelWidget":
    """Generate a view for a model

    :param model_cls: observable (`.observe`) model class
    :param format_label: function to format labels
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param hide_private_traits: show/hide traits prefixed with "_"
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """
    if hide_private_traits:
        can_follow_trait = logical_and(can_follow_trait, is_public_trait)

    ctx = RenderContext(
        format_label=format_label,
        namespace=namespace or {},
        logger=logger,
        visited=set(),
        path=(),
        can_follow_trait=can_follow_trait,
    )
    return _type_has_traits_view_factory(model_cls, ctx)


TraitViewFactoryType = Callable[[traitlets.TraitType, RenderContext], widgets.Widget]
_trait_view_factories: Dict[Type[traitlets.TraitType], TraitViewFactoryType] = {}


def _get_trait_view_factory(
    trait_type: Type[traitlets.TraitType]
) -> TraitViewFactoryType:
    for cls in trait_type.__mro__:
        try:
            return _trait_view_factories[cls]
        except KeyError:
            continue
    raise ValueError(f"Couldn't find factory for {trait_type}")


def create_trait_view(trait: traitlets.TraitType, ctx: RenderContext) -> widgets.Widget:
    """Create a view for a trait

    :param trait: traitlet instance
    :param ctx: render context
    :return:
    """
    factory = _get_trait_view_factory(type(trait))
    return factory(trait, ctx)


def register_trait_view_factory(
    *trait_types: Type[traitlets.TraitType], view_factory: TraitViewFactoryType
):
    """Register a view factory for a given traitlet type(s)

    :param trait_types: trait class(es) to register
    :param view_factory: view factory for trait class(es)
    :return:
    """
    for trait_type in trait_types:
        _trait_view_factories[trait_type] = view_factory


def unregister_trait_view_factory(*trait_types: Type[traitlets.TraitType]):
    """Unregister a view factory for a given traitlet type(s)

    :param trait_types: trait class(es) to unregister
    :return:
    """
    for trait_type in trait_types:
        del _trait_view_factories[trait_type]


def trait_view_factory(*trait_types: Type[traitlets.TraitType]):
    """Decorator for  registering view factory functions

    :param trait_types: trait class(es) to register
    :return:
    """

    def wrapper(factory):
        register_trait_view_factory(*trait_types, view_factory=factory)
        return factory

    return wrapper


class _ModelWidget(widgets.VBox):
    def __init__(self, widgets_: Dict[str, widgets.Widget], logger, **kwargs):
        self.links = []
        self.widgets = widgets_
        self.logger = logger
        super().__init__(tuple(widgets_.values()), **kwargs)

    @classmethod
    def specialise_for_cls(
        cls, klass: Union[Type[traitlets.HasTraits], str]
    ) -> Type["_ModelWidget"]:
        """Create a specialised _ModelWidget for a given class

        :param klass: `HasTraits` subclass or class name
        :return:
        """

        class _ModelWidget(cls):
            value = traitlets.Instance(klass)

        return _ModelWidget

    @traitlets.observe("value")
    def _value_changed(self, change):
        for link in self.links:
            link.unlink()

        model = change["new"]
        self.links.clear()

        for n, w in self.widgets.items():
            try:
                widgets.link((model, n), (w, "value"))
            except:
                if self.logger is not None:
                    self.logger.exception(f"Error in linking widget {n}")


def _type_has_traits_view_factory(
    has_traits: Type[traitlets.HasTraits], ctx: RenderContext
) -> _ModelWidget:
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
            widget = create_trait_view(trait, derived_ctx)
        except:
            ctx.logger.exception(
                f"Unable to render trait {name!r} ({type(trait).__qualname__})"
            )
            continue

        ctx.logger.info(f"Folling trait {name!r}")
        widget.description = (
            ctx.format_label(name) if callable(ctx.format_label) else name
        )
        widget.disabled = trait.read_only
        model_widgets[name] = widget

    model_widget_class = _ModelWidget.specialise_for_cls(has_traits)
    return model_widget_class(model_widgets, ctx.logger)


@trait_view_factory(traitlets.Instance)
def _instance_view_factory(trait: traitlets.Instance, ctx) -> _ModelWidget:
    cls = trait.klass
    if isinstance(cls, str):
        cls = ctx.namespace[cls]

    if not issubclass(cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    return _type_has_traits_view_factory(cls, ctx)


@trait_view_factory(traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName)
def _unicode_view_factory(
    trait: traitlets.TraitType, ctx: RenderContext
) -> widgets.Text:
    return widgets.Text()


@trait_view_factory(traitlets.Enum)
def _enum_view_factory(trait: traitlets.Enum, ctx: RenderContext) -> widgets.Dropdown:
    return widgets.Dropdown(options=sorted(trait.values))


@trait_view_factory(traitlets.Bool)
def _bool_view_factory(trait: traitlets.Bool, ctx: RenderContext) -> widgets.Checkbox:
    return widgets.Checkbox(indent=True)


@trait_view_factory(traitlets.Float)
def _float_view_factory(
    trait: traitlets.Float, ctx: RenderContext
) -> Union[widgets.FloatText, widgets.FloatSlider, widgets.BoundedFloatText]:
    if not (math.isfinite(trait.min) or math.isfinite(trait.max)):
        return widgets.FloatText()
    if math.isfinite(trait.min) and math.isfinite(trait.max):
        return widgets.FloatSlider(min=trait.min, max=trait.max)
    return widgets.BoundedFloatText(min=trait.min, max=trait.max)


@trait_view_factory(traitlets.Integer)
def _integer_view_factory(
    trait: traitlets.Integer, ctx: RenderContext
) -> Union[widgets.IntText, widgets.IntSlider, widgets.BoundedIntText]:
    if trait.min is None and trait.max is None:
        return widgets.IntText()
    elif not (trait.min is None or trait.max is None):
        return widgets.IntSlider(min=trait.min, max=trait.max)
    return widgets.BoundedIntText(min=trait.min, max=trait.max)
