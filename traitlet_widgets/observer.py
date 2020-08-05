from inspect import signature
from logging import getLogger
from typing import Callable

import traitlets

ObserverType = Callable[..., None]
root_logger = getLogger(__name__)


def model_observer(
    model: traitlets.HasTraits, func: ObserverType = None
) -> ObserverType:
    """Observe changes to a model and pass them to the correspondingly named parameters of the function

    :param model: observable (`.observe`) model
    :param func: function to invoke with updates. Leave `None` if using as a decorator
    :return:
    """
    if not isinstance(model, traitlets.HasTraits):
        raise ValueError("Expected `traitlets.HasTraits` instance as first argument.")

    def wrapper(decorated):
        params = signature(decorated).parameters

        for name in params:
            if name not in model.trait_names():
                raise ValueError(
                    f"Observer parameter {name!r} is not defined "
                    f"for model with traits {model.trait_names()}"
                )

        def update_func(change):
            state = {n: getattr(model, n) for n in params}
            decorated(**state)

        for name in params:
            model.observe(update_func, name)
        return decorated

    if func is None:
        return wrapper

    return wrapper(func)
