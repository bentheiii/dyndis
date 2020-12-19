from inspect import isclass, ismodule
from itertools import chain
from types import SimpleNamespace, MappingProxyType
from typing import Callable
from warnings import warn

import builtins
import sys

from dyndis.type_keys.delegates import UnboundDelegate, _raise


class UnboundFriend(UnboundDelegate):
    """
    Searches for a class with a similar name in the type's namespace
    """

    def __init__(self, name_func: Callable[..., str], *type_vars, namespace=..., default=_raise):
        """
        :param name_func: a callable to return the name of the attribute to search for
        :param namespace: the name space to search in, default will search in the namespaces of the types
        :param default: if provided, this value will be returned instead of raising an error
        """
        super().__init__(*type_vars)
        self.name_func = name_func
        self.namespace = namespace
        self.default = default

    def __call__(self, *bound_types: type):
        name = self.name_func(*bound_types)
        if self.namespace is ...:
            mods = []
            for bt in bound_types:
                mod = get_namespaces(bt)
                mods.append(mod)
            ns = JoinedNamespaces.make(mods)
        elif isinstance(self.namespace, str):
            ns = sys.modules[self.namespace]
        elif isinstance(self.namespace, (dict, MappingProxyType)):
            ns = SimpleNamespace(**self.namespace)
        else:
            ns = self.namespace

        try:
            return getattr(ns, name)
        except NameError:
            if self.default is _raise:
                raise
            return self.default

    def __eq__(self, other):
        return type(self) == type(other) and \
               (self.type_vars, self.name_func, self.namespace, self.default) \
               == (other.type_var, other.name_func, other.namespace, other.default)

    def __hash__(self):
        return hash((self.type_vars, self.name_func, self.namespace, self.default))

    def __repr__(self):
        return f'{type(self).__name__}(' \
               + ", ".join(chain((repr(self.name_func),), *(t.__name__ for t in self.type_vars))) \
               + (", namespace=" + repr(self.namespace) if self.namespace is not ... else "") \
               + (", default=" + repr(self.default) if self.default is not _raise else "") \
               + ')'


def get_namespaces(cls: type):
    """
    get the total namespace where a class is defined
    """
    qname = cls.__qualname__
    mod_name = cls.__module__
    if qname.startswith(mod_name):
        qname = qname[len(mod_name):]
    mod = sys.modules[mod_name]
    ret = [builtins, mod]
    for name in qname.split('.'):
        ns = getattr(ret[-1], name, None)
        if ns is None or (not isclass(ns) and not ismodule(ns)):
            break
        ret.append(ns)
    return StackedNamespaces.make(ret)


class CompoundNamespaces:
    """
    A base class for combining namespaces
    """

    def __init__(self, parts):
        self._parts = parts

    @classmethod
    def make(cls, parts):
        """
        create a compound namespace if necessary
        """
        if len(parts) > 1:
            return cls(parts)
        return parts[0]


class StackedNamespaces(CompoundNamespaces):
    """
    A compound namespace where the last namespace has precedence
    """

    def __init__(self, parts):
        super().__init__(parts[::-1])

    def __getattr__(self, item):
        for p in self._parts:
            try:
                return getattr(p, item)
            except AttributeError:
                pass
        raise NameError(item)


class JoinedNamespaces(CompoundNamespaces):
    """
    A compound namespace where the no one has precedence
    """

    def __getattr__(self, item):
        ret = set()
        for p in self._parts:
            try:
                ret.add(getattr(p, item))
            except AttributeError:
                pass
        if not ret:
            raise NameError(item)
        if len(ret) > 1:
            raise NameError(f'multiple conflicting matches for {item}')
        return next(iter(ret))
