from typing import Union, TypeVar, Any

from dyndis.annotation_filter import annotation_filter


def cmp(a, b):
    an_a = annotation_filter(a)
    an_b = annotation_filter(b)
    atb = an_a.envelops(an_b)
    bta = an_b.envelops(an_a)
    if atb and not bta:
        return 1
    if bta and not atb:
        return -1
    if atb and bta:
        return None
    return 0


class A:
    pass


class B(A):
    pass


class D(B):
    pass


class C(A):
    pass


class E(D, C):
    pass


class F(E):
    pass


class G:
    pass


r"""
 A  G
/ \
B C
| |
D |
\ /
 E
 |
 F
"""


def test_cls_cls():
    assert cmp(B, D) > 0
    assert cmp(D, C) == 0
    assert cmp(D, D) is None


def test_union_cls():
    assert cmp(A, Union[B, C]) > 0
    assert cmp(Union[A, B], D) > 0
    assert cmp(Union[B, E], C) == 0
    assert cmp(Union[A, B], A) is None


def test_union_union():
    assert cmp(Union[A, B], Union[B, D]) > 0
    assert cmp(Union[B, G], Union[B, C]) == 0
    assert cmp(Union[B, G], Union[B, G]) is None


def test_constrained_cls():
    assert cmp(TypeVar('T', A, B, D), E) > 0
    assert cmp(A, TypeVar('T', B, C)) > 0
    assert cmp(TypeVar('T', C, B), D) == 0


def test_constrained_union():
    assert cmp(TypeVar('T', B, A), Union[E, D]) > 0
    assert cmp(Union[B, C], TypeVar('T', D, E)) > 0
    assert cmp(Union[B, E], TypeVar('T', A, E)) == 0


def test_constrained_constrained():
    assert cmp(TypeVar('T', B, C), TypeVar('T', E, F)) > 0
    assert cmp(TypeVar('T', B, D), TypeVar('T', C, E)) == 0
    T = TypeVar('T', B, C)
    assert cmp(T, T) is None


def test_bounded_cls():
    assert cmp(A, TypeVar('T', bound=B)) > 0
    assert cmp(C, TypeVar('T', bound=B)) == 0
    assert cmp(B, TypeVar('T', bound=Union[D, F])) > 0


def test_bounded_union():
    assert cmp(Union[B, C], TypeVar('T', bound=E)) > 0
    assert cmp(Union[B, C], TypeVar('T', bound=A)) == 0


def test_bounded_constrained():
    assert cmp(TypeVar('T', B, C), TypeVar('T', bound=F)) > 0
    assert cmp(TypeVar('T', B, C), TypeVar('T', bound=A)) == 0


def test_bounded_bounded():
    assert cmp(TypeVar('T', bound=object), TypeVar('T', bound=bool)) == 0
    T = TypeVar('T', bound=Exception)
    assert cmp(T, T) is None


def test_any():
    assert cmp(A, Any) < 0
    assert cmp(Any, Union[A, B]) > 0
    assert cmp(Any, Any) is None
    assert cmp(Any, object) > 0
