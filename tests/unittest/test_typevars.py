from typing import Sized, TypeVar, Union, Any

from pytest import raises

from dyndis import MultiDispatch, UnboundFriend, UnboundAttr
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.type_keys.type_key import AmbiguousBindingError


def test_simple():
    T = TypeVar('T', bound=Sized)

    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: Sized, b: Sized):
        return len(a) + len(b)

    @foo.add_func()
    def foo(a: T, b: T):
        return len(a) * len(b)

    B = TypeVar('B', bool, type(None))

    @foo.add_func()
    def foo(a: bool, b: bool):
        return a and b

    @foo.add_func()
    def foo(a: B, b: B):
        return a + b

    assert foo('', (1, 2)) == 2
    assert foo('aa', 'bbb') == 6
    assert foo((9, 9, 9), (1, 2, 5)) == 9
    assert foo(True, False) == False


def test_typevar_default():
    T = TypeVar('T', bound=Sized)

    foo = MultiDispatch()

    @foo.add_func()
    def foo(a: T, b: Union[T, tuple] = ()):
        return len(a) * len(b)

    assert foo('aaa') == 0
    assert foo('aa', 'bb') == 4


def test_uncertain_binding():
    class A: pass

    class B: pass

    class C(A, B): pass

    T = TypeVar('T', A, B)
    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T):
        pass

    assert foo(A()) is None
    assert foo(B()) is None

    with raises(AmbiguousBindingError):
        foo(C())


def test_uncertain_binding_solution():
    class A: pass

    class B: pass

    class C(A, B): pass

    T = TypeVar('T', A, B, C)
    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T):
        pass

    assert foo(A()) is None
    assert foo(B()) is None

    assert foo(C()) is None


def test_uncertain_binding_specialization():
    class A: pass

    class B: pass

    class C(A, B): pass

    T = TypeVar('T', A, B)
    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T):
        pass

    @foo.add_func()
    def foo(x: C):
        pass

    assert foo(A()) is None
    assert foo(B()) is None

    assert foo(C()) is None


def test_unbound():
    class A:
        Y = int

    class B:
        Y = str

    T = TypeVar('T', A, B)
    TY = UnboundAttr(T, 'Y')

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T, y: TY):
        pass

    assert foo(A(), 1) is None
    assert foo(B(), 'hi') is None

    with raises(NoCandidateError):
        foo(A(), 'hi')

    with raises(NoCandidateError):
        foo(B(), 15)


def test_unbound_to_union():
    class A:
        Y = Union[int, str]

    class B:
        Y = str

    T = TypeVar('T', A, B)
    TY = UnboundAttr(T, 'Y')

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T, y: TY):
        pass

    assert foo(A(), 1) is None
    assert foo(A(), 'hi') is None
    assert foo(B(), 'hi') is None

    with raises(NoCandidateError):
        foo(B(), 15)


def test_possibilities():
    class A:
        Y = Union[int, str]

    class B:
        Y = str

    T = TypeVar('T', A, B)
    TY = UnboundAttr(T, 'Y')

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T, y: TY):
        return 0

    @foo.add_func()
    def foo(x: T, t: bool):
        return 1

    assert foo(A(), True) == 1


def test_cmp():
    T = TypeVar('T')
    Y = TypeVar('Y')

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T):
        pass

    @foo.add_func()
    def foo(x: Y):
        pass

    with raises(AmbiguityError):
        foo(1)


def test_cmp_pos():
    T = TypeVar('T')

    class A: pass

    class B(A): pass

    class C(B): pass

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T, a: A):
        return 0

    @foo.add_func()
    def foo(x: T, b: B):
        return 1

    assert foo(object(), A()) == 0
    assert foo(object(), B()) == 1
    assert foo(object(), C()) == 1


def test_friend_unbound():
    T = TypeVar('T')

    class IntHandler:
        pass

    class FloatHandler:
        pass

    F = UnboundFriend(lambda x: x.__name__[:-7].lower(), T)

    foo = MultiDispatch()

    @foo.add_func()
    def foo(x: T, a: F):
        return 0

    @foo.add_func()
    def foo(x: Any, a: Any):
        return 1

    assert foo(IntHandler(), 1) == 0
    assert foo(FloatHandler(), 1.0) == 0
    assert foo(IntHandler(), 1.1) == 1
