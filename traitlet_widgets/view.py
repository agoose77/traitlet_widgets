from logging import Logger, getLogger
from typing import Type, Dict, Any, Tuple

import traitlets

from .view_factories import (
    create_widgets_for_model_cls,
    has_traits_view_factory,
    CanFollowTraitType,
    ViewContext,
    TransformerType,
)
from .widgets import ModelViewWidget

logger = getLogger(__name__)


def default_can_follow_trait(model: traitlets.HasTraits, path: Tuple[str, ...]) -> bool:
    return True


def model_view_for(
    model_cls: Type[traitlets.HasTraits],
    transformer: TransformerType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = logger,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
    **kwargs: Dict[str, Any]
) -> "ModelViewWidget":
    """Generate a view for a model

    :param model_cls: observable (`.observe`) model class
    :param transformer: function to visit found members
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """

    ctx = ViewContext(
        transformer=transformer,
        namespace=namespace or {},
        logger=logger,
        visited=set(),
        path=(),
        can_follow_trait=can_follow_trait,
    )
    model_widget_class = ModelViewWidget.specialise_for_cls(model_cls)
    return model_widget_class(ctx, **kwargs)


def model_view(
    model: traitlets.HasTraits,
    transformer: TransformerType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = logger,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
    **kwargs: Dict[str, Any]
) -> "ModelViewWidget":
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param transformer: function to visit found members
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """
    view = model_view_for(
        type(model), transformer, namespace, logger, can_follow_trait, value=model, **kwargs
    )
    return view
