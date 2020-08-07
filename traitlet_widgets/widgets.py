from typing import Type, Union

import ipywidgets as widgets
import traitlets


class ModelViewWidget(widgets.HBox):
    """Widget to render a view over a a model"""

    ctx = traitlets.Instance(object)
    description = traitlets.Unicode()
    disabled = traitlets.Bool(False)
    value = traitlets.Instance(object)

    def __init__(self, ctx, **kwargs):
        self.description_widget = widgets.Label(value=kwargs.get("description", ""))
        widgets.link((self.description_widget, "value"), (self, "description"))

        self._links = []
        self._logger = ctx.logger

        model_widgets = ctx.create_widgets_for_model_cls(
            ctx.resolve(type(self).value.klass)
        )

        shared_trait_names = self.class_traits().keys() & model_widgets.keys()
        if shared_trait_names:
            raise ValueError(
                f"Traits {shared_trait_names} clash with builtin widget trait names"
            )

        self.widgets = model_widgets
        super().__init__(
            children=[
                self.description_widget,
                widgets.VBox(list(model_widgets.values())),
            ],
            **kwargs,
        )

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

    @traitlets.observe("value")
    def _model_changed(self, change):
        for link in self._links:
            link.unlink()
        self._links.clear()

        model = change["new"]
        for n, w in self.widgets.items():
            try:
                self._links.append(widgets.link((model, n), (w, "value")))
                self._links.append(widgets.link((self, "disabled"), (w, "disabled")))
            except:
                if self._logger is not None:
                    self._logger.exception(f"Error in linking widget {n}")
