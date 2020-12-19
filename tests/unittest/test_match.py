from typing import Union, Sequence, TypeVar, Sized, Hashable, Optional, Callable

from pytest import raises

from dyndis.annotation_filter import annotation_filter


def match(ann, x, defined=None):
    defined = defined or {}
    f = annotation_filter(ann)
    return f.match(x, defined)


def test_cls():
    assert match(int, int)
    assert match(int, bool)
    assert not match(int, str)
    assert not match(bool, int)


def test_union():
    assert match(Union[Sequence, int], tuple)
    assert match(Union[Sequence, int], bool)
    assert not match(Union[Sequence, int], float)


def test_union_many():
    assert match(Union[object, int], bool)


def test_union_with_tv():
    T = TypeVar('T', str, bool)
    assert match(Union[int, T], int)
    assert match(Union[int, T], str) == {T: annotation_filter(str)}
    with raises(TypeError):
        match(Union[str, T], str)
    with raises(TypeError):
        match(Union[T, str], str)
    assert match(Union[bool, T], bool, {T: annotation_filter(str)}) is True


def test_tv_constrained():
    T = TypeVar('T', str, bool)
    assert match(T, str) == {T: annotation_filter(str)}
    assert not match(T, int)

    class A(str):
        pass

    assert match(T, A) == {T: annotation_filter(str)}


def test_nested_tv():
    T0 = TypeVar('T0', bound=Sized)
    T1 = TypeVar('T1', int, T0)
    assert match(T1, tuple) == {T0: annotation_filter(tuple), T1: annotation_filter(T0)}


def test_tv_constrained_ambiguous():
    T = TypeVar('T', Sized, Hashable)
    assert match(T, int) == {T: annotation_filter(Hashable)}
    assert match(T, list) == {T: annotation_filter(Sized)}
    with raises(TypeError):
        match(T, tuple)


def test_tv_bounded():
    T = TypeVar('T', bound=Exception)
    assert not match(T, RuntimeError, {T: annotation_filter(TypeError)})
    assert not match(T, int)
    assert match(T, TypeError) == {T: annotation_filter(TypeError)}


def test_tv_nested():
    T0 = TypeVar('T0', int, str)
    T1 = TypeVar('T1', bound=T0)
    assert match(T1, bool) == {T0: annotation_filter(int), T1: annotation_filter(bool)}


def test_optional():
    none_type = type(None)

    assert match(None, none_type)
    assert not match(None, int)

    assert match(Union[int, None], int)
    assert match(Union[int, None], none_type)
    assert not match(Union[int, None], float)
    assert match(Optional[int], int)
    assert match(Optional[int], none_type)
    assert not match(Optional[int], float)


def test_callable():
    class A:
        def __call__(self):
            pass

    assert match(Callable, A)