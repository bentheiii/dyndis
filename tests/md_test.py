from typing import Sized, Union, TypeVar, Any, Sequence
from unittest import TestCase

from dyndis import MultiDispatch, UnboundAttr, Self
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.topological_set import TopologicalSet
from dyndis.type_keys.type_key import AmbiguousBindingError


class GeneralTest(TestCase):
    def test_topology(self):
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: int, b: Sized):
            return a * len(b)

        @foo.add_func()
        def foo(a: int, b: Sequence):
            return a * len(b) * 2

        self.assertEqual(foo(4, "aa"), 16)
        self.assertEqual(foo(4, "a"), 8)
        self.assertEqual(foo(4, set(range(6))), 24)
        self.assertEqual(foo(4, set((1, 2))), 8)

    def test_topology_any(self):
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: Any):
            return 0

        @foo.add_func()
        def foo(a: object):
            return 1

        @foo.add_func()
        def foo(b: Sequence):
            return 2

        @foo.add_func()
        def foo(b: str):
            return 3

        self.assertEqual(foo(4), 1)
        self.assertEqual(foo((1, 2, 3)), 2)
        self.assertEqual(foo('a'), 3)
        self.assertEqual(foo(object()), 1)

    @staticmethod
    def make_hierarchy(n):
        base = object
        ret = []
        for level in range(n):
            class Ret(base):
                depth = level

            Ret.__qualname__ = Ret.__name__ = f'hierarchy[{level}]'

            ret.append(Ret)
            base = Ret
        return ret

    def test_topology_many(self):
        foo = MultiDispatch('foo')
        hierarchy = self.make_hierarchy(10)
        for h in hierarchy:
            def foo_(i: h):
                return

            foo_.depth = h.depth
            foo.add_func(foo_)
        cands = list(foo.candidates())
        self.assertEqual(len(cands), 10)
        for i, c in enumerate(cands):
            self.assertEqual(c.func.depth, 9 - i)

    def test_topology_multid(self):
        foo = MultiDispatch('foo')
        hierarchy = self.make_hierarchy(6)
        coordinates = (
            (3, 1, 3),
            (4, 4, 4),
            (2, 3, 2),
            (2, 2, 3),
            (2, 2, 4),
            (4, 1, 1),
            (0, 0, 3),
            (0, 4, 4)
        )
        funcs = []
        for c in coordinates:
            h0, h1, h2 = (hierarchy[i] for i in c)

            def foo_(i0: h0, i1: h1, i2: h2):
                return

            foo_.ind = len(funcs)
            funcs.append(foo_)

            foo.add_func(foo_)
        cands = foo.candidates_for_types(hierarchy[-1], hierarchy[-1], hierarchy[-1])
        cands = [[c.func.ind for c in l] for l in cands]

        self.assertEqual(len(cands), 4)
        self.assertCountEqual(cands[0], [1])
        self.assertCountEqual(cands[1], [0, 2, 4, 5, 7])
        self.assertCountEqual(cands[2], [3])
        self.assertCountEqual(cands[3], [6])


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

    def test_redundancy(self):
        foo = MultiDispatch()

        @foo.add_func()
        def foo(a: int):
            pass

        with self.assertRaises(ValueError):
            @foo.add_func()
            def foo(a: int):
                pass

        @foo.add_func(priority=1)
        def foo(a: int):
            pass

        with self.assertRaises(ValueError):
            @foo.add_func(priority=1)
            def foo(a: int):
                pass


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

    def test_unbound(self):
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

        self.assertEqual(foo(d, 'a'), 3)
        self.assertEqual(foo(m, 1), 4)


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

        B = TypeVar('B', bool, type(None))

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
        def foo(a: T, b: Union[T, tuple] = ()):
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

    def test_uncertain_binding_specialization(self):
        class A: pass

        class B: pass

        class C(A, B): pass

        T = TypeVar('T', A, B)
        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T):
            pass

        @foo.add_func()
        def foo(x: C):
            pass

        self.assertIsNone(foo(A()))
        self.assertIsNone(foo(B()))

        self.assertIsNone(foo(C()))

    def test_unbound(self):
        class A:
            Y = int

        class B:
            Y = str

        T = TypeVar('T', A, B)
        TY = UnboundAttr(T, 'Y')

        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T, y: TY):
            pass

        self.assertIsNone(foo(A(), 1))
        self.assertIsNone(foo(B(), 'hi'))

        with self.assertRaises(NoCandidateError):
            foo(A(), 'hi')

        with self.assertRaises(NoCandidateError):
            foo(B(), 15)

    def test_unbound_to_union(self):
        class A:
            Y = Union[int, str]

        class B:
            Y = str

        T = TypeVar('T', A, B)
        TY = UnboundAttr(T, 'Y')

        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T, y: TY):
            pass

        self.assertIsNone(foo(A(), 1))
        self.assertIsNone(foo(A(), 'hi'))
        self.assertIsNone(foo(B(), 'hi'))

        with self.assertRaises(NoCandidateError):
            foo(B(), 15)

    def test_cmp(self):
        T = TypeVar('T')
        Y = TypeVar('Y')

        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T):
            pass

        @foo.add_func()
        def foo(x: Y):
            pass

        with self.assertRaises(AmbiguityError):
            foo(1)

    def test_cmp_pos(self):
        T = TypeVar('T')

        class A: pass

        class B(A): pass

        class C(B): pass

        foo = MultiDispatch()

        @foo.add_func()
        def foo(x: T, a: A):
            return 0

        @foo.add_func()
        def foo(x: T, b: B):
            return 1

        self.assertEqual(foo(object(), A()), 0)
        self.assertEqual(foo(object(), B()), 1)
        self.assertEqual(foo(object(), C()), 1)


class TopologicalSetTests(TestCase):
    class Divnum(int):
        def __lt__(self, other):
            return other % self == 0

    def assertLayers(self, ts: TopologicalSet, layers):
        self.assertEqual([set(i) for i in ts.layers()],
                         layers)

    def test_simple(self):
        ts = TopologicalSet([self.Divnum(i) for i in (1, 6, 11, 18, 306, 17)])
        self.assertLayers(ts,
                          [
                              {1},
                              {6, 11, 17},
                              {18},
                              {306}
                          ])

        ts.remove(6)
        self.assertLayers(ts,
                          [
                              {1},
                              {18, 11, 17},
                              {306}
                          ])

    def test_removal(self):
        ts = TopologicalSet([self.Divnum(i) for i in (1, 2, 3, 6, 12, 18)])
        self.assertLayers(ts,
                          [
                              {1},
                              {2, 3},
                              {6},
                              {12, 18}
                          ])
        ts.remove(6)
        self.assertLayers(ts,
                          [
                              {1},
                              {2, 3},
                              {12, 18}
                          ])
