from functools import partial

from dyndis.exceptions import NoCandidateError


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


_no_answer = object()


class MultiDispatchRaisingDelegate(MultiDispatchDelegate):
    def __call__(self, *args, **kwargs):
        ret = self.md.get(args, kwargs, default=_no_answer)
        if ret is _no_answer:
            raise NoCandidateError(args)
        return ret


class MultiDispatchMethod(MultiDispatchRaisingDelegate):
    """
    A method adapter for a MultiDispatch
    """

    def __get__(self, instance, owner):
        if instance:
            return partial(self.__call__, instance)
        return self


class MultiDispatchClassMethod(MultiDispatchRaisingDelegate):
    """
    A static method adapter for a MultiDispatch
    """

    def __get__(self, instance, owner):
        return partial(self.__call__, owner)


class MultiDispatchStaticMethod(MultiDispatchRaisingDelegate):
    """
    A static method adapter for a MultiDispatch
    """

    def __get__(self, instance, owner):
        return self
