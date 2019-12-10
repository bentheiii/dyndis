from typing import TypeVar, Any, Union

from dyndis import MultiDispatch, UnboundAttr

foo = MultiDispatch()

T = TypeVar('T')


@foo.add_func()
def foo(a: T):
    return 0


@foo.add_func()
def foo(a: int):
    return 1


print(foo(15))
