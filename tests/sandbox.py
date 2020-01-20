from typing import TypeVar, Any, Union

from dyndis import MultiDispatch, UnboundAttr

foo = MultiDispatch()

T = TypeVar('T')


@foo.add_func()
def foo(a: int):
    return 1


@foo.add_func()
def foo(a: int, b: int):
    return 2


#print(foo())
print(foo(15))
print(foo(15, 2))
