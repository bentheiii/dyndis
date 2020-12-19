from __future__ import annotations

from pytest import warns, mark

from dyndis import MultiDispatch


def test_implementors_override():
    @MultiDispatch
    def foo(self, x):
        return None

    class A:
        @foo.implement(__qualname__)
        def _(self, x: object):
            return 1

        @foo.implement(__qualname__)
        def _(self, x: int):
            return 2

    class B:
        @foo.implement(__qualname__)
        def _(self, x: B):
            return 3

    assert foo(A(), 3) == 2
    assert foo(A(), 'str') == 1
    assert foo(B(), B()) == 3
    assert foo(B(), A()) is None


def test_implementors_both_alive():
    @MultiDispatch
    def foo(self, x):
        return None

    class A:
        @foo.implement(__qualname__)
        def _0(self, x: object):
            return 1

        @foo.implement(__qualname__)
        def _1(self, x: int):
            return 2

    class B:
        @foo.implement(__qualname__)
        def _(self, x: B):
            return 3

    assert foo(A(), 3) == 2
    assert foo(A(), 'str') == 1
    assert foo(B(), B()) == 3
    assert foo(B(), A()) is None


def test_warning():
    @MultiDispatch
    def foo(self):
        return None

    with warns(RuntimeWarning):
        class A:
            @foo.implement(__qualname__)
            def _(self):
                pass

            def _(self):
                pass


@mark.parametrize('classmethod_', [classmethod, lambda x: x])
def test_class_implementor(classmethod_):
    class M(type):
        pass

    @MultiDispatch
    def foo(t):
        return 0

    class A(M):
        @foo.implement(__qualname__)
        @classmethod_
        def _(cls):
            return 1

    class B(M):
        pass

    assert foo(A) == 1
    assert foo(B) == 1
    assert foo(0) == 0


def test_implementor_params():
    @MultiDispatch
    def foo(t, x):
        return 0

    class A:
        @foo.implement(__qualname__, default_annotations={'x': int})
        def _(self, x):
            return 1

    a = A()
    assert foo(a, 12) == 1
    assert foo(a, '') == 0
    assert foo(12, 12) == 0
