from typing import TypeVar

from dyndis import MultiDispatch

foo = MultiDispatch()


class A: pass


class B: pass


class C(A, B): pass


T = TypeVar('T', A, B)


@foo.add_func()
def foo(a: T):
    pass


@foo.add_func()
def foo(a: C):
    pass


foo(C())

print(", ".join(str(c) for c in foo.candidates()))
