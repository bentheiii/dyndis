from typing import Sized, Any, Sequence

from pytest import raises

from dyndis import MultiDispatch


def test_topology():
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: int, b: Sized):
        return a * len(b)

    @foo.add_func()
    def foo(a: int, b: Sequence):
        return a * len(b) * 2

    assert foo(4, "aa") == 16
    assert foo(4, "a") == 8
    assert foo(4, set(range(6))) == 24
    assert foo(4, set((1, 2))) == 8


def test_topology_any():
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

    assert foo(4) == 1
    assert foo((1, 2, 3)) == 2
    assert foo('a') == 3
    assert foo(object()) == 1


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


def test_topology_many():
    foo = MultiDispatch('foo')
    hierarchy = make_hierarchy(10)
    for h in hierarchy:
        def foo_(i: h):
            return

        foo_.depth = h.depth
        foo.add_func(foo_)
    cands = list(foo.candidates())
    assert len(cands) == 10
    for i, c in enumerate(cands):
        assert c.func.depth == 9 - i


def test_topology_multid():
    foo = MultiDispatch('foo')
    hierarchy = make_hierarchy(6)
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

    cands = list(foo.candidates_for_types(hierarchy[-1], hierarchy[-1], hierarchy[-1]))
    cands = [[c.func.ind for c in l] for l in cands]

    assert cands == [[1], [0, 2, 4, 5, 7], [3], [6]]


def test_topology_prio():
    foo = MultiDispatch()

    class A0: pass

    class A1: pass

    class A(A0, A1): pass

    class B0: pass

    class B1: pass

    class B(B0, B1): pass

    log = []

    @foo.add_func(1)
    def foo(a: A):
        log.append(0)
        return NotImplemented

    @foo.add_func()
    def foo(b: B):
        log.append(1)
        return NotImplemented

    @foo.add_func(2)
    def foo(a0: A0):
        log.append(2)
        return NotImplemented

    @foo.add_func(1)
    def foo(b0: B0):
        log.append(3)
        return NotImplemented

    @foo.add_func()
    def foo(a1: A1):
        log.append(4)
        return NotImplemented

    @foo.add_func(-1)
    def foo(b1: B1):
        log.append(5)

    class C(A, B): pass

    assert foo(C()) is None
    assert log == list(range(6))


def test_simple():
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: int, b: Sized = "aaaa"):
        return a * len(str(b))

    @foo.add_func()
    def foo(a: int, b: int, c: float = 2):
        return a * int(b) * c

    assert foo(4) == 16
    assert foo(4, 3) == 24
    assert foo(4, (1, 2)) == 4 * 6
    assert foo(4, 2) == 16
    assert foo(4, 2, 3) == 24


def test_redundancy():
    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: int):
        pass

    with raises(ValueError):
        @foo.add_func()
        def foo(a: int):
            pass

    @foo.add_func(priority=1)
    def foo(a: int):
        pass

    with raises(ValueError):
        @foo.add_func(priority=1)
        def foo(a: int):
            pass
