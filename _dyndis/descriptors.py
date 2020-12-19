from functools import partial


class MultiDispatchDelegate:
    """
    A base class for multidispatch delegates
    """

    def __init__(self, md):
        self.md = md

    def __set_name__(self, owner, name):
        if not self.md.__name__:
            self.md.__name__ = name


class MultiDispatchOp(MultiDispatchDelegate):
    """
    An operator adapter for a MultiDispatch
    """

    def __get__(self, instance, owner):
        if instance:
            return partial(self.__call__, instance)
        return self

    def __call__(self, *args, **kwargs):
        return self.md.get(args, kwargs, default=NotImplemented)
