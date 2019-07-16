import math
from dataclasses import dataclass
from logging import Logger
from typing import Callable, Type, Dict, Any, Union

import ipywidgets as widgets
import traitlets
from inspect import signature

ObserverType = Callable[..., None]


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


def model_view(
    model: traitlets.HasTraits,
    show_private_traits: bool = False,
    label_formatter: Callable[[str], str] = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = None,
) -> '_ModelWidget':
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param show_private_traits: show/hide traits prefixed with "_"
    :param label_formatter: function to format labels
    :param namespace: namespace for lookups
    :param logger: logger to use
    :return:
    """
    ctx = RenderContext(
        show_private_traits=show_private_traits,
        label_formatter=label_formatter,
        namespace=namespace or {},
        logger=logger,
    )
    view = _type_has_traits_view_factory(type(model), ctx)
    view.value = model
    return view


def model_view_for(
    model_cls: Type[traitlets.HasTraits],
    show_private_traits: bool = False,
    label_formatter: Callable[[str], str] = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = None,
) -> '_ModelWidget':
    """Generate a view for a model

    :param model_cls: observable (`.observe`) model class
    :param show_private_traits: show/hide traits prefixed with "_"
    :param label_formatter: function to format labels
    :param namespace: namespace for lookups
    :param logger: logger to use
    :return:
    """
    ctx = RenderContext(
        show_private_traits=show_private_traits,
        label_formatter=label_formatter,
        namespace=namespace or {},
        logger=logger,
    )
    return _type_has_traits_view_factory(model_cls, ctx)


@dataclass
class RenderContext:
    show_private_traits: bool
    namespace: Dict[str, Any]
    label_formatter: Callable[[str], str]
    logger: Logger


TraitViewFactoryType = Callable[[traitlets.TraitType, RenderContext], widgets.Widget]
_trait_view_factories: Dict[Type[traitlets.TraitType], TraitViewFactoryType] = {}


def _get_trait_view_factory(trait_type: Type[traitlets.TraitType]):
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

    def __init__(self, widgets_: Dict[str, widgets.Widget], **kwargs):
        self.links = []
        self.widgets = widgets_
        super().__init__(tuple(widgets_.values()), **kwargs)

    @classmethod
    def specialise_for_cls(cls, klass: Union[Type[traitlets.HasTraits], str]) -> Type['_ModelWidget']:
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
        self.links = [widgets.link((model, n), (w, 'value')) for n, w in self.widgets.items()]


def _type_has_traits_view_factory(has_traits: Type[traitlets.HasTraits], ctx) -> _ModelWidget:
    model_widgets = {}
    for name, trait in has_traits.class_traits().items():
        label = ctx.label_formatter(name) if callable(ctx.label_formatter) else name
        if name.startswith("_") and not ctx.show_private_traits:
            continue

        # Support externally registered widgets
        try:
            widget = create_trait_view(trait, ctx)
        except:
            if ctx.logger:
                ctx.logger.exception(
                    f"Unable to render {name} ({type(trait).__qualname__})"
                )
            continue

        widget.description = label
        widget.disabled = trait.read_only
        model_widgets[name] = widget

    model_widget_class = _ModelWidget.specialise_for_cls(has_traits)
    return model_widget_class(model_widgets)


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
