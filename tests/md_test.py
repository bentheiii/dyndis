from typing import Sized, Union, TypeVar, Any
from unittest import TestCase

from dyndis.candidate import Self

from dyndis import MultiDispatch
from dyndis.exceptions import AmbiguousBindingError


class DefaultTest(TestCase):
    def test_simple(self):
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: int, b: Sized = "aaaa"):
            return a * len(str(b))

        @foo.add_func()
        def foo(a: int, b: int, c: float = 2):
            return a * int(b) * c

        self.assertEqual(foo(4), 16)
        self.assertEqual(foo(4, 3), 24)
        self.assertEqual(foo(4, (1, 2)), 4 * 6)
        self.assertEqual(foo(4, 2), 16)
        self.assertEqual(foo(4, 2, 3), 24)


class ExampleTests(TestCase):
    def test_simple(self):
        t1 = "overload 1 <int, (int, str)>"
        t2 = "overload 2 <any, float>"
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: int, b: Union[int, str]):
            return t1

        @foo.add_func()
        def foo(a: object, b: float):
            return t2

        self.assertEqual(foo(1, "hello"), t1)
        self.assertEqual(foo(("any", "object", "here"), 2.5), t2)
        self.assertEqual(foo(2, 3), t1)
        self.assertEqual(foo(2, 3.0), t2)

    def test_implementor(self):
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
        self.assertEqual(a + b, 'A+B')
        self.assertEqual(a + base, 'A+Base')
        self.assertEqual(a + a, 'A+A')
        self.assertEqual(b + a, 'B+A')

    def test_symmetric(self):
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
        self.assertEqual(a + b, 'A+B/B+A')
        self.assertEqual(b + a, 'A+B/B+A')

    def test_self(self):
        foo = MultiDispatch('foo')

        class A:
            @foo.implementor()
            def foo_(self, other: bool):
                return "bool"

            @foo_.implementor()
            def foo_(self, other: Union[Self, str]):
                return "A or str"

        a = A()
        self.assertEqual(foo(a, False), "bool")
        self.assertEqual(foo(a, a), "A or str")

    def test_tv(self):
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

        self.assertEqual(foo(1, 1), t1)  # <=
        self.assertEqual(foo(1, True), t1)  # <=
        self.assertEqual(foo(2, 'a'), t2)  # </=
        self.assertEqual(foo(object(), object()), t1)  # <=
        self.assertEqual(foo(False, 2), t2)  # </=


class TypeVarTest(TestCase):
    def test_simple(self):
        T = TypeVar('T', bound=Sized)

        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: Sized, b: Sized):
            return len(a) + len(b)

        @foo.add_func()
        def foo(a: T, b: T):
            return len(a) * len(b)

        B = TypeVar('B', bool, float)

        @foo.add_func()
        def foo(a: bool, b: bool):
            return a and b

        @foo.add_func()
        def foo(a: B, b: B):
            return a + b

        self.assertEqual(foo('', (1, 2)), 2)
        self.assertEqual(foo('aa', 'bbb'), 6)
        self.assertEqual(foo((9, 9, 9), (1, 2, 5)), 9)
        self.assertEqual(foo(True, False), False)

    def test_typevar_default(self):
        T = TypeVar('T', bound=Sized)

        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: T, b: T = ()):
            return len(a) * len(b)

        self.assertEqual(foo('aaa'), 0)
        self.assertEqual(foo('aa', 'bb'), 4)

    def test_uncertain_binding(self):
        class A: pass

        class B: pass

        class C(A, B): pass

        T = TypeVar('T', A, B)
        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T):
            pass

        self.assertIsNone(foo(A()))
        self.assertIsNone(foo(B()))

        with self.assertRaises(AmbiguousBindingError):
            foo(C())

    def test_uncertain_binding_solution(self):
        class A: pass

        class B: pass

        class C(A, B): pass

        T = TypeVar('T', A, B, C)
        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T):
            pass

        self.assertIsNone(foo(A()))
        self.assertIsNone(foo(B()))

        self.assertIsNone(foo(C()))
