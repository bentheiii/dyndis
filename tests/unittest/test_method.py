from dyndis import MultiDispatch


def test_as_method():
    @MultiDispatch
    def foo(self, x):
        return 0

    class A:
        bar = foo

    @foo.register
    def _(self: A, x: int):
        return 1

    @foo.register
    def _(self: A, x: str):
        return 2

    @foo.register
    def _(self: int, x: int):
        return 3

    a = A()
    assert a.bar(12) == 1
    assert a.bar("12") == 2
    assert a.bar(0.2) == 0
    assert A.bar(12, 12) == 3
    assert A.bar(a, 12) == 1


def test_as_classmethod():
    @MultiDispatch
    def foo(cls, x):
        return 0

    class A:
        bar = classmethod(foo)

    @foo.register
    def _(cls: type, x: int):
        return 1

    @foo.register
    def _(cls: type, x: str):
        return 2

    @foo.register
    def _(cls: int, x: int):
        return 3

    a = A()
    assert a.bar(12) == 1
    assert a.bar("12") == 2
    assert a.bar(0.2) == 0
    assert A.bar(12) == 1


def test_as_staticmethod():
    @MultiDispatch
    def foo(self, x):
        return 0

    class A:
        bar = staticmethod(foo)

    @foo.register
    def _(self: A, x: int):
        return 1

    @foo.register
    def _(self: A, x: str):
        return 2

    @foo.register
    def _(self: int, x: int):
        return 3

    a = A()
    assert a.bar(a, 12) == 1
    assert a.bar(a, "12") == 2
    assert a.bar(a, 0.2) == 0
    assert A.bar(12, 12) == 3
    assert A.bar(a, 12) == 1
