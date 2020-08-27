from typing import Tuple

import traitlets

from .types import FilterType


def logical_and(left, right):
    """Logically combine functions with the same signature using AND"""

    def and_(*args, **kwargs) -> bool:
        return left(*args, **kwargs) and right(*args, **kwargs)

    return and_


def logical_or(left, right):
    """Logically combine functions with the same signature using OR"""

    def or_(*args, **kwargs) -> bool:
        return left(*args, **kwargs) or right(*args, **kwargs)

    return or_


class BooleanExpression:
    """High level interface to combine boolean operators"""

    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs) -> bool:
        return self.func(*args, **kwargs)

    def __and__(self, other):
        return self.__class__(logical_and(self.func, other))

    def __or__(self, other):
        return self.__class__(logical_or(self.func, other))


boolean_expression = BooleanExpression


@boolean_expression
def is_public_trait(
    model: traitlets.HasTraits, path: Tuple[str, ...], trait: traitlets.TraitType
) -> bool:
    return not path[-1].startswith("_")


@boolean_expression
def is_own_trait(
    model: traitlets.HasTraits, path: Tuple[str, ...], trait: traitlets.TraitType
) -> bool:
    return path[-1] in model.class_own_traits()


def is_whitelisted(*paths: Tuple[str]) -> FilterType:
    whitelist = set(paths)

    @boolean_expression
    def wrapper(
        model: traitlets.HasTraits, path: Tuple[str, ...], trait: traitlets.TraitType
    ) -> bool:
        return path in whitelist

    return wrapper


def is_not_blacklisted(*paths: Tuple[str]) -> FilterType:
    blacklist = set(paths)

    @boolean_expression
    def wrapper(
        model: traitlets.HasTraits, path: Tuple[str, ...], trait: traitlets.TraitType
    ) -> bool:
        return path not in blacklist

    return wrapper
