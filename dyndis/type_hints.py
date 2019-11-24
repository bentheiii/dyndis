from functools import lru_cache
from typing import TypeVar, Callable, Union, Any, Optional

from abc import ABC, abstractmethod

from dyndis.exceptions import AmbiguousBindingError

_raise = object()


class UnboundDelegate(ABC, Callable[[type], type]):
    def __init__(self, type_var: TypeVar):
        self.type_var = type_var

    @abstractmethod
    def __call__(self, bound_type: type) -> type:
        return Nil


class UnboundAttr(UnboundDelegate):
    def __init__(self, type_var: TypeVar, attribute: str, default=_raise):
        super().__init__(type_var)
        self.attribute = attribute
        self.default = default

    def __call__(self, bound_type: type):
        ret = getattr(bound_type, self.attribute, self.default)
        if ret is _raise:
            raise AttributeError(self.attribute)
        return ret

    def __eq__(self, other):
        return type(self) == type(other) and \
               (self.type_var, self.attribute, self.default) == (other.type_var, other.attribute, other.default)

    def __hash__(self):
        return hash((self.type_var, self.attribute, self.default))

    def __repr__(self):
        if self.default is _raise:
            return f'{type(self).__name__}({self.type_var.__name__}, {self.attribute!r})'
        if self.default is _raise:
            return f'{type(self).__name__}({self.type_var.__name__}, {self.attribute!r}, {self.default!r})'


@lru_cache
def constrain_type(cls, scls: Union[type, TypeVar, type(Any)]) -> Optional[type]:
    """
    get the lowest type that cls can be up-cast to and scls accepts as constraint. Or None if none exists.
    """
    if scls is Any:
        return cls
    elif isinstance(scls, TypeVar):
        if scls.__constraints__:
            candidates = [c for c in scls.__constraints__ if issubclass(cls, c)]
            if not candidates:
                return None
            minimal_candidates = [
                cand for cand in candidates if all(issubclass(cand, c) for c in candidates)
            ]
            if len(minimal_candidates) != 1:
                raise AmbiguousBindingError(scls, cls, minimal_candidates or candidates)
            return minimal_candidates[0]
        elif scls.__bound__:
            return constrain_type(cls, scls.__bound__)
        return cls
    return cls if issubclass(cls, scls) else None


def issubclass_tv(cls, scls):
    """
    :return: True if cls can be upcast to a type that fits in scls's type constraints
    """
    return constrain_type(cls, scls) is not None


def cmp_type_hint(r: Union[type, TypeVar], l: Union[type, TypeVar]) -> Optional[int]:
    """
    can return 4 values:
    0 if they are identical
    -1 if r <= l
    1 if l <= r
    None if they cannot be compared
    """
    def similar_sign(i):
        """
        check that all values in iterable are equal, with 0 being an "any" value.

        :return: the common member of the iterable, or None if any are None or no single common sign is found
        """
        ret = 0
        for i in i:
            if i is None:
                return None
            if ret == 0:
                ret = i
            elif i == 0:
                continue
            elif ret != i:
                return None
        return ret

    if not isinstance(r, type):
        if isinstance(r, TypeVar):
            if r.__bound__:
                return cmp_type_hint(r.__bound__, l)
            elif r.__constraints__:
                return similar_sign(cmp_type_hint(c, l) for c in r.__constraints__)
            else:
                return cmp_type_hint(object, l)
        elif r is Any:
            return int(l is not Any)
        elif isinstance(r, UnboundDelegate):
            return None
        else:
            raise TypeError
    elif not isinstance(l, type):
        i_cth = cmp_type_hint(l, r)
        return i_cth and -i_cth
    else:  # both are types
        if r is l:
            return 0
        elif issubclass(r, l):
            return -1
        elif issubclass(l, r):
            return 1
        return None


class Nil:
    def __new__(cls):
        raise TypeError('cannot instantiate instance of class Nil')

    def __init_subclass__(cls, **kwargs):
        raise TypeError('cannot subclass Nil')
