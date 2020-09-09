import math
from logging import getLogger

import ipywidgets as widgets
import traitlets

from .factory import trait_view_variants, ViewFactoryContext
from .traits import Callable
from .types import VariantIterator
from .widgets import CallableButton, ModelViewWidget

default_logger = getLogger(__name__)


@trait_view_variants(traitlets.Instance)
def instance_view_factory(
    trait: traitlets.Instance, ctx: ViewFactoryContext
) -> VariantIterator:
    model_cls = ctx.resolve(trait.klass)

    if issubclass(model_cls, traitlets.HasTraits):
        model_view_cls = ModelViewWidget.specialise_for_cls(model_cls)
        yield model_view_cls, {"ctx": ctx, **ctx.metadata}


@trait_view_variants(
    traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName
)
def unicode_view_factory(
    trait: traitlets.TraitType, ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.ColorPicker, ctx.metadata
    yield widgets.Combobox, ctx.metadata
    yield widgets.HTML, ctx.metadata
    yield widgets.HTMLMath, ctx.metadata
    yield widgets.Label, ctx.metadata
    yield widgets.Password, ctx.metadata
    yield widgets.Textarea, ctx.metadata
    yield widgets.Text, ctx.metadata


@trait_view_variants(traitlets.Enum)
def enum_view_factory(
    trait: traitlets.Enum, ctx: ViewFactoryContext
) -> VariantIterator:
    params = {"options": trait.values, **ctx.metadata}

    yield widgets.SelectionSlider, params
    yield widgets.RadioButtons, params
    yield widgets.Select, params
    yield widgets.ToggleButtons, params
    yield widgets.Dropdown, params


@trait_view_variants(traitlets.Bool)
def bool_view_factory(
    trait: traitlets.Bool, ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.ToggleButton, ctx.metadata
    yield widgets.Checkbox, {"indent": True, **ctx.metadata}
    if trait.read_only:
        yield widgets.Valid, ctx.metadata


@trait_view_variants(traitlets.Float)
def float_view_factory(
    trait: traitlets.Float, ctx: ViewFactoryContext
) -> VariantIterator:
    # Unbounded variant
    yield widgets.FloatText, ctx.metadata

    # Build UI params store
    params = {"min": trait.min, "max": trait.max, **ctx.metadata}

    # Require min to be set & finite
    if params["min"] is None or not math.isfinite(params["min"]):
        return

    # Require max to be set & finite
    if params["max"] is None or not math.isfinite(params["max"]):
        return

    # Bounded variants:
    yield widgets.BoundedFloatText, params
    yield widgets.FloatSlider, params

    # Logarithmic bounded variant
    if params.get("base") is not None:
        params["min"] = math.log(params["min"], params["base"])
        params["max"] = math.log(params["max"], params["base"])
        yield widgets.FloatLogSlider, params


@trait_view_variants(traitlets.Integer)
def integer_view_factory(
    trait: traitlets.Integer, ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.IntText, ctx.metadata

    params = {"min": trait.min, "max": trait.max, **ctx.metadata}
    if params["min"] is None or params["max"] is None:
        return

    yield widgets.Play, ctx.metadata
    yield widgets.BoundedIntText, params
    yield widgets.IntSlider, params


@trait_view_variants(Callable)
def callable_variant_factory(trait, ctx):
    yield CallableButton, ctx.metadata