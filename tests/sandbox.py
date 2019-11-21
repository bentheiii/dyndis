from typing import TypeVar, Union

from dyndis import MultiDispatch

foo = MultiDispatch()

T = TypeVar('T')
R = TypeVar('R')


@foo.add_func()
def foo(a: T, b: R, c: Union[T, R]):
    return 0 if isinstance(c, type(a)) else 1


print(foo(1, 2.5, 2.0j))
