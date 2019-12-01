from typing import TypeVar, Any, Union

from dyndis import MultiDispatch, UnboundAttr

foo = MultiDispatch()

T = TypeVar('T')
TI = UnboundAttr(T, 'I')


@foo.add_func()
def foo(a: object):
    return 'obj'


@foo.add_func()
def foo(a: Any):
    return 'any'

@foo.add_func()
def foo(b: Union[T, T], a: TI):
    return 'any'


print(list(foo.candidates()))
print(", ".join(str(c[0]) for c in foo.candidates_for(int)))
