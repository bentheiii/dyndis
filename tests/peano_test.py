from unittest import TestCase

from tests.peano import unit, n


class PeanoTests(TestCase):
    def test_inc(self):
        two = unit + unit
        three = two + unit
        five = two + three
        self.assertEqual(five.value(), 5)

    def test_arithmetic(self):
        one_and_a_half = n(3) / n(2)
        one_third = n(1) / n(3)
        one_sixth = n(1) / (n(12) / n(2))
        self.assertEqual((-(one_and_a_half - one_third - one_sixth)).value(), -1)
