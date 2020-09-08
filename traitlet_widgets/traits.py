import traitlets


class Callable(traitlets.TraitType):
    """A callable trait.

    Used as a decorator, e.g
    >>> @Callable
    >>> def func(self):
    >>>     pass
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def validate(self, obj, value):
        # Similar to traitlets.Callable, but invoke `__get__` on callable
        if callable(value):
            return value.__get__(obj, type(obj))
        else:
            self.error(obj, value)
