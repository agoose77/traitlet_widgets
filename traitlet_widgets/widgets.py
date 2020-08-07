from typing import Dict, Type, Union

import ipywidgets as widgets
import traitlets


class ModelViewWidget(widgets.HBox):
    """Widget to render a view over a a model"""

    value = traitlets.Instance(object)
    ctx = traitlets.Instance(object)
    description = traitlets.Unicode()

    def __init__(self, ctx, **kwargs):
        self.description_widget = widgets.Label()
        widgets.link((self.description_widget, 'value'), (self, 'description'))

        self._links = []
        self._logger = ctx.logger

        from .view_factories import create_widgets_for_model_cls
        model_widgets = create_widgets_for_model_cls(type(self).value.klass, ctx)

        if "value" in model_widgets:
            raise ValueError("Trait name 'value' not permitted in model")

        self.widgets = model_widgets
        super().__init__(children=[self.description_widget, widgets.VBox(list(model_widgets.values()))], **kwargs)

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
            except:
                if self._logger is not None:
                    self._logger.exception(f"Error in linking widget {n}")

