from typing import Iterator, List, Type, Union

import ipywidgets as widgets
import traitlets


class CallableButton(widgets.Button):
    def link_to_model(self, model, view, name):
        func = getattr(model, name)
        self.on_click(lambda _: func())

        # Allow widget to be disabled if model is
        yield widgets.dlink((view, "disabled"), (self, "disabled"))


class ModelViewWidget(widgets.HBox):
    """Widget to render a view over a a model"""

    ctx = traitlets.Instance(object)
    description = traitlets.Unicode()
    disabled = traitlets.Bool(False)
    value = traitlets.Instance(object)

    def __init__(self, **kwargs):
        # Create description label
        self.description_label = widgets.Label(value=kwargs.get("description", ""))
        widgets.link((self.description_label, "value"), (self, "description"))

        # Create vbox for widgets
        self.widgets_vbox = widgets.VBox()

        # Create widgets
        value_trait = self.traits()["value"]
        ctx = kwargs["ctx"]
        self.widgets = ctx.create_widgets_for_model_cls(ctx.resolve(value_trait.klass))
        self.widgets_vbox.children = list(self.widgets.values())
        self._links = []

        self._logger = ctx.logger

        shared_trait_names = self.class_traits().keys() & self.widgets.keys()
        if shared_trait_names:
            raise ValueError(
                f"Traits {shared_trait_names} clash with builtin widget trait names"
            )

        super().__init__(
            children=[
                self.description_label,
                self.widgets_vbox,
            ],
            **kwargs,
        )

    def _link_widget_to_model(
        self, name: str, widget: widgets.Widget, model: traitlets.HasTraits
    ) -> Iterator[traitlets.link]:
        """Link a single widget to a model.

        Respect read-only relationships, and delegate linking to widget if it
        implements the necessary interface.

        :param name: name of model field
        :param widget: widget instance
        :param model: model instance
        :return:
        """
        # Allow widget to handle linking
        if hasattr(widget, "link_to_model"):
            yield from widget.link_to_model(model, self, name)
            return

        # Infer read-only state from initial widget disabled state
        is_read_only = getattr(widget, "disabled", False)
        link_factory = widgets.dlink if is_read_only else widgets.link

        # Allow widget to be disabled when container is disabled
        if hasattr(widget, "disabled") and not is_read_only:
            yield widgets.dlink((self, "disabled"), (widget, "disabled"))

        yield link_factory((model, name), (widget, "value"))

    def _link_widgets_to_model(
        self, model: traitlets.HasTraits
    ) -> Iterator[traitlets.link]:
        """Create traitlet links between model and widgets

        :param model: model instance
        :return:
        """
        for name, widget in self.widgets.items():
            try:
                yield from self._link_widget_to_model(name, widget, model)
            except:
                self._logger.exception(f"Error in linking widget {name}")

    @traitlets.observe("value")
    def _update_model_links(self, change):
        for link in self._links:
            link.unlink()
        self._links.clear()

        model = change["new"]
        with model.hold_trait_notifications():
            self._links = [*self._link_widgets_to_model(model)]

    @classmethod
    def specialise_for_cls(
        cls, klass: Union[Type[traitlets.HasTraits], str]
    ) -> Type["ModelViewWidget"]:
        """Create a specialised _ModelWidget for a given class

        :param klass: `HasTraits` subclass or class name
        :return:
        """
        klass_name = getattr(klass, "__name__", klass)
        return type(f"{klass_name}View", (cls,), {"value": traitlets.Instance(klass)})
