from typing import Any, NamedTuple

try:
    # get_origin and get_args are only defined in 3.8
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


class SubPriority:
    """
    A generic priority with a secondary modifier
    """

    @classmethod
    def make(cls, x, weight=-1):
        """
        create a sub-priority
        """
        if weight == 0:
            return x
        return cls(x, weight)

    def __init__(self, original, weight):
        self.original = original
        self.weight = weight
        self.key = (self.original, self.weight)

    @classmethod
    def to_key(cls, x):
        """
        force x into a key that can be compared with self.key
        """
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

    def __eq__(self, other):
        return self.key == self.to_key(other)

    def __hash__(self):
        return hash(self.key)


def liberal_cache(func):
    """
    create a memoized function that simply ignores un-hashable values
    """
    cache = {}

    def ret(arg):
        try:
            return cache[arg]
        except TypeError:
            return func(arg)
        except KeyError:
            pass
        res = cache[arg] = func(arg)
        return res

    return ret
