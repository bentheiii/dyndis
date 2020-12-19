from __future__ import annotations

from abc import abstractmethod, ABC
from functools import total_ordering
from typing import Union

from dyndis import MultiDispatch


@MultiDispatch
def add(self, other):
    return NotImplemented


@MultiDispatch
def lt(self, other):
    return NotImplemented


@total_ordering
class Num(ABC):
    @abstractmethod
    def value(self):
        pass

    __add__ = __radd__ = add
    __lt__ = lt


class Zero(Num):
    def value(self):
        return 0

    @add.implement(__qualname__)
    def _(self, other: Num):
        return other

    @lt.implement(__qualname__)
    def _(self, other: Zero):
        return False

    def __eq__(self, other):
        return self is other


zero = Zero()


class Positive(Num):
    def __init__(self, pred: Union[Zero, Positive]):
        self.pred = pred

    def value(self):
        return self.pred.value() + 1

    @add.implement(__qualname__)
    def _(self, other: Positive):
        return self.pred + Positive(other)

    @lt.implement(__qualname__)
    def _(self, other: Zero):
        return False

    @lt.implement(__qualname__)
    def _(self, other: Positive):
        return self.pred < other.pred


class Negative(Num):
    def __init__(self, pred: Union[Zero, Negative]):
        self.pred = pred

    def value(self):
        return self.pred.value() - 1

    @add.implement(__qualname__)
    def _(self, other: Positive):
        return self.pred + other.pred

    @add.implement(__qualname__)
    def _(self, other: Negative):
        return self.pred + Negative(other)

    @lt.implement(__qualname__)
    def _(self, other: Union[Zero, Positive]):
        return True

    @lt.implement(__qualname__)
    def _(self, other: Negative):
        return self.pred < other.pred


def from_int(x: int) -> Num:
    if x == 0:
        return zero
    if x > 0:
        ret = zero
        for _ in range(x):
            ret = Positive(ret)
        return ret
    if x < 0:
        ret = zero
        for _ in range(-x):
            ret = Negative(ret)
        return ret


def test_arith():
    assert (from_int(3) + from_int(2)).value() == 5
    assert (from_int(-3) + from_int(1)).value() == -2
    assert (from_int(4) + from_int(-3)).value() == 1


def test_comp():
    assert from_int(3) < from_int(5)
    assert from_int(-1) > from_int(-3)
    assert from_int(0) >= from_int(-3)
    assert from_int(-3) >= from_int(-3)
