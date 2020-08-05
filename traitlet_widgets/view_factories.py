import dataclasses
import math
from logging import Logger, getLogger
from typing import Any, Callable, Dict, Type, Tuple, Union

import ipywidgets as widgets
import traitlets

from .widgets import HasTraitsViewWidget

logger = getLogger(__name__)


CanFollowTraitType = Callable[[traitlets.HasTraits, Tuple[str, ...]], bool]


VisitorType = Callable[
    [traitlets.HasTraits, Tuple[str, ...], traitlets.TraitType, widgets.Widget], None
]


@dataclasses.dataclass
class ViewContext:
    namespace: Dict[str, Any]
    visitor: VisitorType
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

    def visit(
        self,
        model: traitlets.HasTraits,
        name: str,
        trait: traitlets.TraitType,
        widget: widgets.Widget,
    ):
        """Call the user defined visitor with a given model field

        :param model:
        :param name:
        :param trait:
        :param widget:
        :return:
        """
        path = self.resolve_name(name)

        if callable(self.visitor):
            self.visitor(model, path, trait, widget)


TraitViewFactoryType = Callable[[traitlets.TraitType, ViewContext], widgets.Widget]
_trait_view_factories: Dict[Type[traitlets.TraitType], TraitViewFactoryType] = {}


def create_trait_view(
    trait: traitlets.TraitType, ctx: ViewContext, description: str = None
) -> widgets.Widget:
    """Create a view for a trait

    :param trait: traitlet instance
    :param ctx: render context
    :param description: label description
    :return:
    """
    factory = _get_trait_view_factory(type(trait))
    widget = factory(trait, ctx)

    # Set description (set by model)
    if description is not None:
        widget.description = description

    # Set any useful values using metadata
    for key, value in trait.metadata.items():
        if hasattr(widget, key):
            logger.debug("Setting {trait} metadata {key} = {value!r} on {widget}")
            setattr(widget, key, value)

    widget.disabled = trait.read_only
    return widget


def _get_trait_view_factory(
    trait_type: Type[traitlets.TraitType],
) -> TraitViewFactoryType:
    """Get a view factory for a given trait class

    :param trait_type: trait class
    :return:
    """
    for cls in trait_type.__mro__:
        try:
            return _trait_view_factories[cls]
        except KeyError:
            continue
    raise ValueError(f"Couldn't find factory for {trait_type}")


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


def has_traits_view_factory(
    has_traits: Type[traitlets.HasTraits], ctx: ViewContext
) -> HasTraitsViewWidget:
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
            widget = create_trait_view(
                trait, derived_ctx, description=name.replace("_", " ").title()
            )
        except:
            ctx.logger.exception(
                f"Unable to render trait {name!r} ({type(trait).__qualname__})"
            )
            continue

        ctx.visit(has_traits, name, trait, widget)

        ctx.logger.info(f"Folling trait {name!r}")
        model_widgets[name] = widget

    model_widget_class = HasTraitsViewWidget.specialise_for_cls(has_traits)
    return model_widget_class(model_widgets, ctx.logger)


@trait_view_factory(traitlets.Instance)
def _instance_view_factory(trait: traitlets.Instance, ctx) -> HasTraitsViewWidget:
    cls = trait.klass
    if isinstance(cls, str):
        cls = ctx.namespace[cls]

    if not issubclass(cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    return has_traits_view_factory(cls, ctx)


@trait_view_factory(traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName)
def _unicode_view_factory(trait: traitlets.TraitType, ctx: ViewContext) -> widgets.Text:
    return widgets.Text()


@trait_view_factory(traitlets.Enum)
def _enum_view_factory(trait: traitlets.Enum, ctx: ViewContext) -> widgets.Dropdown:
    return widgets.Dropdown(options=sorted(trait.values))


@trait_view_factory(traitlets.Bool)
def _bool_view_factory(trait: traitlets.Bool, ctx: ViewContext) -> widgets.Checkbox:
    return widgets.Checkbox(indent=True)


@trait_view_factory(traitlets.Float)
def _float_view_factory(
    trait: traitlets.Float, ctx: ViewContext
) -> Union[widgets.FloatText, widgets.FloatSlider, widgets.BoundedFloatText]:
    if not (math.isfinite(trait.min) or math.isfinite(trait.max)):
        return widgets.FloatText()
    if math.isfinite(trait.min) and math.isfinite(trait.max):
        return widgets.FloatSlider(min=trait.min, max=trait.max)
    return widgets.BoundedFloatText(min=trait.min, max=trait.max)


@trait_view_factory(traitlets.Integer)
def _integer_view_factory(
    trait: traitlets.Integer, ctx: ViewContext
) -> Union[widgets.IntText, widgets.IntSlider, widgets.BoundedIntText]:
    if trait.min is None and trait.max is None:
        return widgets.IntText()
    elif not (trait.min is None or trait.max is None):
        return widgets.IntSlider(min=trait.min, max=trait.max)
    return widgets.BoundedIntText(min=trait.min, max=trait.max)
