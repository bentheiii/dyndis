from gc import collect
from weakref import ref

from dyndis.weaktupledict import WeakTupleDict


class A:
    pass


def test_wtd():
    wtd = WeakTupleDict()
    a = A()
    b = A()
    r_b = ref(b)
    wtd[a, b] = 0
    assert len(wtd) == 1
    assert wtd[a, b] == 0
    assert wtd.get((a, a), None) is None
    assert wtd.get((a, b)) == 0
    del b
    collect()
    assert r_b() is None
    assert len(wtd) == 0


def test_double_del():
    wtd = WeakTupleDict()
    a = A()
    b = A()
    r_a = ref(a)
    r_b = ref(b)
    wtd[a, b] = 0
    assert len(wtd) == 1
    del b
    collect()
    assert r_b() is None
    del a
    assert r_a() is None
    collect()
    assert len(wtd) == 0


def test_same_tuple():
    wtd = WeakTupleDict()
    a = A()
    r_a = ref(a)
    wtd[a, a] = 0
    assert len(wtd) == 1
    del a
    collect()
    assert r_a() is None
    assert len(wtd) == 0
