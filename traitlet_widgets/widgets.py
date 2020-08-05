from typing import Dict, Type, Union

import ipywidgets as widgets
import traitlets


class HasTraitsViewWidget(widgets.VBox):
    """Widget to render a view over a a model"""

    model = traitlets.Instance(object)

    def __init__(self, widgets_: Dict[str, widgets.Widget], logger, **kwargs):
        self.links = []
        self.widgets = widgets_
        self.logger = logger
        super().__init__(tuple(widgets_.values()), **kwargs)

    @classmethod
    def specialise_for_cls(
        cls, klass: Union[Type[traitlets.HasTraits], str]
    ) -> Type["HasTraitsViewWidget"]:
        """Create a specialised _ModelWidget for a given class

        :param klass: `HasTraits` subclass or class name
        :return:
        """
        klass_name = getattr(klass, "__name__", klass)
        return type(f"{klass_name}View", (cls,), {"model": traitlets.Instance(klass)})

    @traitlets.observe("model")
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
