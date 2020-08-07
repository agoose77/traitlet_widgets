from logging import Logger, getLogger
from typing import Type, Dict, Any, Tuple

import traitlets

from .view_factories import (
    FilterType,
    ViewFactory,
    TransformerType,
)
from .widgets import ModelViewWidget

default_logger = getLogger(__name__)


def model_view(
    model: traitlets.HasTraits,
    transform_trait: TransformerType = None,
    filter_trait: FilterType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = default_logger,
    **kwargs: Dict[str, Any]
) -> "ModelViewWidget":
    factory = ViewFactory(
        filter_trait=filter_trait,
        transform_trait=transform_trait,
        namespace=namespace,
        logger=logger,
    )
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param transform_trait: function to visit found members
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param filter_trait: condition function to determine whether to follow traits by path
    :return:
    """
    return factory.create_root_view(model, metadata=kwargs)
