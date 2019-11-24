from typing import TypeVar, Any

from dyndis import MultiDispatch

foo = MultiDispatch()


class A: pass


class B: pass


class C(A, B): pass


T = TypeVar('T', A, B)


@foo.add_func()
def foo(a: object):
    return 'obj'


@foo.add_func()
def foo(a: Any):
    return 'any'


print(list(foo.candidates()))
print(", ".join(str(c) for c in foo.candidates()))
