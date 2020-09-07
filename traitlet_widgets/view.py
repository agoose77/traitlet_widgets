from logging import Logger, getLogger
from typing import Dict, Any

import traitlets

from .factory import ViewFactory
from .types import FilterType
from .widgets import ModelViewWidget

default_logger = getLogger(__name__)


def model_view(
    model: traitlets.HasTraits,
    filter_trait: FilterType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = default_logger,
    metadata: Dict[str, Any] = None,
    **kwargs: Any
) -> "ModelViewWidget":
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param filter_trait: condition function to determine whether to follow traits by path
    :return:
    """
    factory = ViewFactory(
        filter_trait=filter_trait, namespace=namespace, logger=logger, metadata=metadata
    )
    return factory.create_root_view(model, **kwargs)
