from abc import ABC
from typing import Union, TypeVar

from pytest import raises

from dyndis import MultiDispatch, AmbiguityError


def test_basic_onearg():
    @MultiDispatch
    def foo(x):
        return None

    @foo.register
    def _(x: int):
        return 1

    @foo.register
    def _(x: str):
        return 2

    @foo.register
    def _(x: bool):
        return 3

    assert foo(15) == 1
    assert foo("15") == 2
    assert foo("") == 2
    assert foo(15.2) is None
    assert foo(object()) is None
    assert foo(True) == 3


def test_union_simple():
    @MultiDispatch
    def foo(x):
        return None

    @foo.register
    def _(x: Union[type, int]):
        return 0

    @foo.register
    def _(x: bool):
        return 1

    assert foo(True) == 1
    assert foo(1) == 0


def test_ambiguity():
    @MultiDispatch
    def foo(x):
        return None

    @foo.register
    def _(x: Union[type, bool]):
        return 0

    @foo.register
    def _(x: Union[str, bool]):
        return 1

    assert foo(object) == 0
    with raises(AmbiguityError):
        foo(True)


def test_typevar_simple():
    @MultiDispatch
    def foo(x, y):
        return False

    T = TypeVar('T')

    @foo.register
    def _(x: T, y: T):
        return True

    assert foo(1, 1)
    assert not foo(True, 1)
    assert foo(1, True)


def test_typevar_constrained():
    @MultiDispatch
    def foo(x, y):
        return None

    T = TypeVar('T', str, int)

    @foo.register
    def _(x: T, y: T):
        return True

    assert foo(1, 1)
    assert foo(True, 1)
    assert foo(1, True)
    assert not foo("True", 1)


def test_typevar_fallback():
    @MultiDispatch
    def foo(x, y):
        return 0

    T = TypeVar('T', str, int)

    @foo.register
    def _(x: T, y: T):
        return 1

    @foo.register
    def _(x: Union[str, int], y: object):
        return 2

    assert foo(1, 1) == 1
    assert foo(True, 1) == 1
    assert foo(1, "hi") == 2
    assert foo("True", 1) == 2


def test_abc_register():
    class A(ABC):
        pass

    class B:
        pass

    @MultiDispatch
    def foo(*args, **kwargs):
        return 0

    @foo.register
    def _(a: A):
        return 1

    b = B()

    assert foo(b) == 0

    A.register(B)

    assert foo(b) == 1
