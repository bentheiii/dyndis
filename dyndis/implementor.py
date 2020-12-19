from collections import ChainMap
from functools import update_wrapper
from types import MethodDescriptorType
from typing import Callable, List, NamedTuple, Dict, Any, Optional
from warnings import warn


class PendingImplementation(NamedTuple):
    func: Callable
    md: Any
    kwargs: Optional[Dict[str, Any]]

    def chain_kwargs(self, **parents: ChainMap):
        if not self.kwargs:
            return parents

        ret = dict(self.kwargs)
        for k, parent in parents.items():
            child = ret.get(k)
            if not child:
                ret[k] = parent
            else:
                ret[k] = parent.new_child(child)
        return ret


class Implementor:
    def __init__(self):
        self.queue: List[PendingImplementation] = []
        self.done = False

    def commit(self, cls: type):
        if self.done:
            return
        self.done = True
        default_annotations = ChainMap({'self': cls, 'cls': type(cls)})
        extra_namespace = ChainMap({cls.__name__: cls})
        for queued in self.queue:
            kwargs = queued.chain_kwargs(
                default_annotations=default_annotations,
                extra_namespace=extra_namespace,
            )
            queued.md.register(
                queued.func,
                **kwargs
            )

    def __call__(self, md, kwargs, func):
        if isinstance(func, classmethod):
            func = func.__func__

        self.queue.append(PendingImplementation(func, md, kwargs))
        return ImplementorWrapper(self, func)

    def __del__(self):
        if not self.done:
            warn(RuntimeWarning('implementor deleted without registering implementations'))


class ImplementorWrapper:
    def __init__(self, implementor: Implementor, func: MethodDescriptorType):
        self.implementor = implementor
        self.inner = func
        update_wrapper(self, func)

    def __set_name__(self, owner, name):
        self.implementor.commit(owner)
        self.implementor = None
        setattr(owner, name, self.inner)

    # although the wrapper does its best to self-destruct, it might still be held as the function, so we have it
    # imitate its inner value as much as we can

    def __get__(self, instance, owner):
        return self.inner.__get__(instance, owner)

    def __call__(self, *args, **kwargs):
        return self.inner(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self.inner, item)
