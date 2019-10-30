from typing import Any, NamedTuple


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
    pass
