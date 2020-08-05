from logging import Logger, getLogger
from typing import Type, Dict, Any, Tuple

import traitlets

from .view_factories import (
    has_traits_view_factory,
    CanFollowTraitType,
    ViewContext,
    VisitorType,
)
from .widgets import HasTraitsViewWidget

logger = getLogger(__name__)


def default_can_follow_trait(model: traitlets.HasTraits, path: Tuple[str, ...]) -> bool:
    return True


def model_view_for(
    model_cls: Type[traitlets.HasTraits],
    visitor: VisitorType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = logger,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
) -> "HasTraitsViewWidget":
    """Generate a view for a model

    :param model_cls: observable (`.observe`) model class
    :param visitor: function to visit found members
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """

    ctx = ViewContext(
        visitor=visitor,
        namespace=namespace or {},
        logger=logger,
        visited=set(),
        path=(),
        can_follow_trait=can_follow_trait,
    )
    return has_traits_view_factory(model_cls, ctx)


def model_view(
    model: traitlets.HasTraits,
    visitor: VisitorType = None,
    namespace: Dict[str, Any] = None,
    logger: Logger = logger,
    can_follow_trait: CanFollowTraitType = default_can_follow_trait,
) -> "HasTraitsViewWidget":
    """Generate a view for a model

    :param model: observable (`.observe`) model
    :param visitor: function to visit found members
    :param namespace: namespace for lookups
    :param logger: logger to use
    :param can_follow_trait: condition function to determine whether to follow traits by path
    :return:
    """
    view = model_view_for(type(model), visitor, namespace, logger, can_follow_trait,)
    view.model = model
    return view
