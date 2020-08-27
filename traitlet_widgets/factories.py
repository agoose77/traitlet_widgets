import math
from logging import getLogger
from typing import Any, Dict

import ipywidgets as widgets
import traitlets

from .factory import trait_view_variants, ViewFactoryContext
from .types import VariantIterator
from .widgets import ModelViewWidget

default_logger = getLogger(__name__)


@trait_view_variants(traitlets.Instance)
def _instance_view_factory(
    trait: traitlets.Instance, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    model_cls = ctx.resolve(trait.klass)

    if not issubclass(model_cls, traitlets.HasTraits):
        raise ValueError("Cannot render a non-traitlet model")

    model_view_cls = ModelViewWidget.specialise_for_cls(model_cls)
    yield model_view_cls, {"ctx": ctx, **metadata}


@trait_view_variants(
    traitlets.Unicode, traitlets.ObjectName, traitlets.DottedObjectName
)
def _unicode_view_factory(
    trait: traitlets.TraitType, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.Text, metadata


@trait_view_variants(traitlets.Enum)
def _enum_view_factory(
    trait: traitlets.Enum, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    params = {"options": sorted(trait.values), **metadata}

    yield widgets.SelectionSlider, params
    yield widgets.Dropdown, params


@trait_view_variants(traitlets.Bool)
def _bool_view_factory(
    trait: traitlets.Bool, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.Checkbox, {"indent": True, **metadata}


@trait_view_variants(traitlets.Float)
def _float_view_factory(
    trait: traitlets.Float, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    # Unbounded variant
    yield widgets.FloatText, metadata

    # Build UI params store
    params = {"min": trait.min, "max": trait.max, **metadata}

    # Require min to be set
    if params["min"] is None or not math.isfinite(params["min"]):
        return

    # Require max to be set
    if params["max"] is None or not math.isfinite(params["max"]):
        return

    # Bounded variants:
    yield widgets.BoundedFloatText, params
    yield widgets.FloatSlider, params

    # Logarithmic bounded variant
    if params.get("base") is not None:
        yield widgets.FloatLogSlider, params


@trait_view_variants(traitlets.Integer)
def _integer_view_factory(
    trait: traitlets.Integer, metadata: Dict[str, Any], ctx: ViewFactoryContext
) -> VariantIterator:
    yield widgets.IntText, metadata

    params = {"min": trait.min, "max": trait.max, **metadata}
    if params["min"] is None or params["max"] is None:
        return

    yield widgets.BoundedIntText, params
    yield widgets.IntSlider, params
