from typing import TypeVar, Any, Union

from dyndis import MultiDispatch, UnboundAttr

foo = MultiDispatch()


class A:
    T = Union[int, str]


class B:
    T = int


T = TypeVar('T', A, B)


@foo.add_func()
def foo(a: T, x: UnboundAttr(T, 'T')):
    return 0


@foo.add_func()
def foo(a: T, x: int):
    return 1


print(foo.potential_conflicts().display())
print(foo(A(), 15))
