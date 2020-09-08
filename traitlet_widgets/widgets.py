from typing import List, Type, Union

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

    def _create_links_to_model(self, model: traitlets.HasTraits) -> List[traitlets.link]:
        """Create traitlet links between model and widgets

        :param model:
        :return:
        """
        for n, w in self.widgets.items():
            try:
                # Allow widget to handle linking
                if hasattr(w, "link_to_model"):
                    yield from w.link_to_model(model, self, n)
                else:
                    yield widgets.link((model, n), (w, "value"))

                    # Allow widget to be disabled if model is
                    if hasattr(w, "disabled"):
                        yield widgets.dlink((self, "disabled"), (w, "disabled"))

            except:
                if self._logger is not None:
                    self._logger.exception(f"Error in linking widget {n}")

    @traitlets.observe("value")
    def _update_model_links(self, change):
        for link in self._links:
            link.unlink()
        self._links.clear()

        model = change["new"]
        with model.hold_trait_notifications():
            self._links = list(self._create_links_to_model(model))

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
