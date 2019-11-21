from functools import lru_cache
from typing import Any, NamedTuple, TypeVar, Optional, Union

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


class AmbiguityError(RuntimeError):
    """An error indicating that a multidispatch had to decide between candidates of equal precedence"""

    def __init__(self, candidates, types):
        cands = "[" + ", ".join(str(c) for c in candidates) + "]"
        super().__init__(
            f'multiple candidates of equal precedence: {cands} for key <' + ", ".join(t.__name__ for t in types) + ">")


class NoCandidateError(TypeError):
    """An error indicating that a multidispatch has no applicable candidates"""

    def __init__(self, args):
        super().__init__('no valid candidates for argument types <' + ", ".join(type(a).__name__ for a in args) + '>')


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
            ret = None
            for c in scls.__constraints__:
                if not issubclass(cls, c):
                    continue
                if not ret or issubclass(c, ret):
                    ret = c
            return ret
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
