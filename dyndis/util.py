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

    def __init__(self, candidates, types):
        super().__init__(f'multiple candidates of equal precedence: {candidates} for key <' + ", ".join(
            t.__name__ for t in types) + ">")


class NoCandidateError(TypeError):
    """An error indicating that a multidispatch has no applicable candidates"""

    def __init__(self, args):
        super().__init__('no valid candidates for argument types <' + ", ".join(type(a).__name__ for a in args) + '>')
