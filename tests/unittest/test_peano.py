from tests.unittest.peano import unit, n, Number


def test_inc():
    two = unit + unit
    three = two + unit
    five = two + three
    assert five.value() == 5


def test_arithmetic():
    one_and_a_half = n(3) / n(2)
    one_third = n(1) / n(3)
    one_sixth = n(1) / (n(12) / n(2))
    assert (-(one_and_a_half - one_third - one_sixth)).value() == -1


def test_class_op():
    assert Number.__add__(unit, unit).value() == 2
