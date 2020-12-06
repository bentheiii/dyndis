from typing import Sized, Union, TypeVar, Any, Sequence
from unittest import TestCase

from dyndis import MultiDispatch, UnboundAttr, Self, UnboundFriend
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.type_keys.type_key import AmbiguousBindingError


def test_simple():
    t1 = "overload 1 <int, (int, str)>"
    t2 = "overload 2 <any, float>"
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: int, b: Union[int, str]):
        return t1

    @foo.add_func()
    def foo(a: object, b: float):
        return t2

    assert foo(1, "hello") == t1
    assert foo(("any", "object", "here"), 2.5) == t2
    assert foo(2, 3) == t1
    assert foo(2, 3.0) == t2


def test_implementor():
    class Base:
        add = MultiDispatch()
        __add__ = add.op()  # MultiDispatch.op() returns a delegate descriptor that acts as an operator

    class A(Base):
        @Base.add.implementor()
        def add(self, other):
            # in implementor methods, any parameter without a type hint is assumed to be of the owner class
            return "A+A"

        @add.implementor()
        def add(self, other: Base):
            return "A+Base"

    class B(Base):
        @Base.add.implementor()
        def add(self, other: A):
            return 'B+A'

        @add.implementor()
        def add(other: A, self):
            # this isn't pretty, we'll see how to circumvent this later
            return 'A+B'

    a = A()
    b = B()
    base = Base()
    assert a + b == 'A+B'
    assert a + base == 'A+Base'
    assert a + a == 'A+A'
    assert b + a == 'B+A'


def test_symmetric():
    class Base:
        add = MultiDispatch()
        __add__ = add.op()  # MultiDispatch.op() returns a delegate descriptor that acts as an operator

    class A(Base):
        ...

    class B(Base):
        @Base.add.implementor(symmetric=True)
        def add(self, other: A):
            return 'A+B/B+A'

    a = A()
    b = B()
    assert a + b == 'A+B/B+A'
    assert b + a == 'A+B/B+A'


def test_self():
    foo = MultiDispatch('foo')

    class A:
        @foo.implementor()
        def foo_(self, other: bool):
            return "bool"

        @foo_.implementor()
        def foo_(self, other: Union[Self, str]):
            return "A or str"

    a = A()
    assert foo(a, False) == "bool"
    assert foo(a, a) == "A or str"


def test_tv():
    t1 = "type(b) <= type(a)"
    t2 = "type(b) </= type(a"

    T = TypeVar('T')
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: T, b: T):
        return t1

    @foo.add_func()
    def foo(a: Any, b: Any):
        return t2

    assert foo(1, 1) == t1  # <=
    assert foo(1, True) == t1  # <=
    assert foo(2, 'a') == t2  # </=
    assert foo(object(), object()) == t1  # <=
    assert foo(False, 2) == t2  # </=


def test_unbound():
    class StrDict(dict):
        I = str

    class MyList(list):
        I = int

    T = TypeVar('T', StrDict, MyList)
    T_I = UnboundAttr(T, 'I')
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: T, i: T_I):
        return a[i]

    d = StrDict(a=3, b=4)
    m = MyList([3, 4])

    assert foo(d, 'a') == 3
    assert foo(m, 1) == 4
