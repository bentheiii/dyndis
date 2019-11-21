from functools import lru_cache
from typing import Any, NamedTuple, TypeVar, Optional, Union

from dyndis.exceptions import AmbiguousBindingError

try:
    from typing import get_origin, get_args
except ImportError:
    def get_origin(tp):
        return getattr(tp, '__origin__', None)


    def get_args(tp):
        return getattr(tp, '__args__', ())


class RawReturnValue(NamedTuple):
    """
    A class to wrap otherwise special return values from a multidispatch candidate
    """
    inner: Any

    @classmethod
    def unwrap(cls, x):
        """
        If x is a RawReturnValue, return its inner value, if not, return x unchanged
        """
        if isinstance(x, cls):
            return x.inner
        return x


def similar(i):
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


@lru_cache
def constrain_type(cls, scls: Union[type, TypeVar]) -> Optional[type]:
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
                raise AmbiguousBindingError(scls, cls, minimal_candidates)
            return minimal_candidates[0]
        elif scls.__bound__:
            return constrain_type(cls, scls.__bound__)
        return cls
    return cls if issubclass(cls, scls) else None


def issubclass_tv(cls, scls):
    return constrain_type(cls, scls) is not None


class SubPriority:
    @classmethod
    def make(cls, x, weight=-1):
        if weight == 0:
            return x
        if isinstance(x, cls):
            return cls(x.original, x.weight + weight)
        return cls(x, weight)

    def __init__(self, original, weight):
        self.original = original
        self.weight = weight
        self.key = (self.original, self.weight)

    @classmethod
    def to_key(cls, x):
        if isinstance(x, cls):
            return x.key
        return x, 0

    def __lt__(self, other):
        return self.key < self.to_key(other)

    def __le__(self, other):
        return self.key <= self.to_key(other)

    def __gt__(self, other):
        return self.key > self.to_key(other)

    def __ge__(self, other):
        return self.key >= self.to_key(other)


def cmp_type_hint(r: Union[type, TypeVar], l: Union[type, TypeVar]):
    """
    can return 4 values:
    0 if they are identical
    -1 if r <= l
    1 if l <= r
    None if they cannot be compared
    """
    if isinstance(r, TypeVar):
        if r.__bound__:
            return cmp_type_hint(r.__bound__, l)
        elif r.__constraints__:
            return similar(cmp_type_hint(c, l) for c in r.__constraints__)
        else:
            return cmp_type_hint(object, l)
    elif isinstance(l, TypeVar):
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
