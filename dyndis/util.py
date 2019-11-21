from typing import Any, NamedTuple, TypeVar


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


def passes_typevar_bounds(cls, type_var: TypeVar):
    if type_var.__constraints__:
        return any(issubclass_tv(cls, c) for c in type_var.__constraints__)
    elif type_var.__bound__:
        return issubclass_tv(cls, type_var.__bound__)
    return True


def issubclass_tv(cls, scls):
    if scls is Any:
        return True
    if isinstance(scls, TypeVar):
        return passes_typevar_bounds(cls, scls)
    return issubclass(cls, scls)
