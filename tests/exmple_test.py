from typing import Union
from unittest import TestCase

from dyndis import MultiDispatch, Self


class ExampleTests(TestCase):
    Text1 = "overload 1 <int, (int, str)>"
    Text2 = "overload 2 <any, float>"

    def test_simple(self):
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: int, b: Union[int, str]):
            return self.Text1

        @foo.add_func()
        def foo(a: object, b: float):
            return self.Text2

        self.assertEqual(foo(1, "hello"), self.Text1)
        self.assertEqual(foo(("any", "object", "here"), 2.5), self.Text2)
        self.assertEqual(foo(2, 3), self.Text1)
        self.assertEqual(foo(2, 3.0), self.Text2)

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
            def _0(self, other: bool):
                return "bool"

            @foo.implementor()
            def _1(self, other: Union[Self, str]):
                return "A or str"

        a = A()
        self.assertEqual(foo(a, False), "bool")
        self.assertEqual(foo(a, a), "A or str")
