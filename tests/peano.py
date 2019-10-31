from abc import abstractmethod, ABC
from typing import Dict, Any, Tuple, Union

from dyndis import MultiDispatch

add = MultiDispatch()
mul = MultiDispatch()
sub = MultiDispatch()
div = MultiDispatch()
lt = MultiDispatch()
mod = MultiDispatch()


class Number(ABC):
    __add__ = add.op()
    __mul__ = mul.op()
    __sub__ = sub.op()
    __truediv__ = div.op()
    __mod__ = mod.op()
    __lt__ = lt.op()

    def __abs__(self):
        if self < neutral:
            return -self
        return self

    def __eq__(self, other):
        return isinstance(self - other, Neutral)

    def __le__(self, other):
        delt = self - other
        return delt == neutral or delt < neutral

    def __gt__(self, other):
        return other < self

    def __ge__(self, other):
        delt = self - other
        return delt == neutral or delt > neutral

    @abstractmethod
    def value(self):
        return None

    @abstractmethod
    def __neg__(self) -> 'Number':
        pass

    def __str__(self):
        return f'n({self.value()})'

    @lt.implementor(priority=-1)
    def lt(self, other):
        return (self - other) < neutral

    @sub.implementor(priority=-1)
    def sub(self, other):
        return self + (-other)


class Neutral(Number):
    def value(self):
        return 0

    def __neg__(self):
        return self

    @add.implementor(symmetric=True)
    def add(self, b: Number):
        return b

    @lt.implementor()
    def lt(self, other):
        return False

    @sub.implementor(priority=1)
    def sub(other: Number, self):
        return other

    @sub.implementor()
    def sub(self, other: Number):
        return -other

    @mul.implementor(symmetric=True)
    def mul(self, other: Number):
        return self

    @mod.implementor(priority=1)
    def mod(self, other: Number):
        if isinstance(other, Neutral):
            return NotImplemented
        return self

    @div.implementor()
    def div(self, other: Number):
        if isinstance(other, Neutral):
            return NotImplemented
        return self


neutral = Neutral()


class Inc(Number):
    def __init__(self, pred):
        self.pred = pred

    def __neg__(self):
        return Neg(self)

    def value(self):
        return self.pred.value() + 1

    @add.implementor()
    def add(self, other):
        return Inc(self) + other.pred

    @lt.implementor()
    def lt(self, other: Neutral):
        return False

    @lt.implementor()
    def lt(other: Neutral, self):
        return True

    @sub.implementor()
    def sub(self, other):
        return self.pred - other.pred

    @mul.implementor()
    def mul(self, other):
        return self + (self * other.pred)

    @mod.implementor()
    def mod(other: Number, self):
        if other < neutral:
            return self - ((-other) % self)
        if other < self:
            return other
        return (other - self) % self

    @div.implementor()
    def div(self, other):
        def floor_div(a, b):
            if isinstance(a, Neutral):
                return a
            return unit + floor_div(a - b, b)

        if other == unit:
            return self
        if self == other:
            return unit
        g = gcd(self, other)
        if g == unit:
            return Rational(self, other)
        return floor_div(self, g) / floor_div(other, g)


unit = Inc(neutral)


class Neg(Number):
    def __init__(self, pos):
        self.pos = pos

    def value(self):
        return -self.pos.value()

    def __neg__(self):
        return self.pos

    @add.implementor(symmetric=True)
    def add(self, a: Number):
        return a - -self

    @add.implementor()
    def add(self, other):
        return -((-self) + (-other))

    @lt.implementor()
    def lt(self, other: Union[Neutral, Inc]):
        return True

    @lt.implementor()
    def lt(other: Union[Neutral, Inc], self):
        return False

    @sub.implementor()
    def sub(other: Number, self):
        return other + (-self)

    @sub.implementor()
    def sub(self, other: Number):
        return -((-self) + other)

    @sub.implementor()
    def sub(self, other):
        return (-other) - (-self)

    @mul.implementor(symmetric=True)
    def mul(self, other: Number):
        return -((-self) * other)

    @div.implementor(priority=1)
    def div(self, other: Number):
        return -((-self) / other)

    @div.implementor()
    def div(other: Number, self):
        return -(self / (-other))


class Rational(Number):
    def __init__(self, n: Union[Inc, Neg], d: Inc):
        self.n = n
        self.d = d

    def value(self):
        return self.n.value() / self.d.value()

    def parts(self) -> Tuple[Union[Inc, Neg], Inc, Inc]:
        m = (self.n % self.d)
        return (self.n - m) / self.d, m, self.d

    def __neg__(self):
        return Rational(-self.n, self.d)

    def __str__(self):
        w, n, d = self.parts()
        if isinstance(w, Neutral):
            return f'n({n.value()}/{d.value()})'
        return f'n({w.value()} {n.value()}/{d.value()})'

    @add.implementor(symmetric=True)
    def add(self, a: Union[Inc, Neg]):
        n = a * self.d + self.n
        return n / self.d

    @add.implementor()
    def add(self, other):
        n = self.n * other.d + self.d * other.n
        return n / (self.d * other.d)

    @lt.implementor()
    def lt(self, other: Neutral):
        return self.n < other

    @sub.implementor()
    def sub(self, other):
        n = self.n * other.d - self.d * other.n
        return n / (self.d * other.d)


def gcd(a, b):
    if a < neutral:
        a = -a
    if b < neutral:
        b = -b

    if b < a:
        a, b = b, a

    while not isinstance(a, Neutral):
        b, a = a, (b % a)
    return b


_n_cache: Dict[Any, Number] = {0: neutral}
top_inc = 0


def fill_naturals(target):
    global top_inc
    prev = _n_cache[top_inc]
    for i in range(top_inc + 1, target + 1):
        prev = _n_cache[i] = Inc(prev)
    top_inc = target


def _n(x):
    if isinstance(x, int):
        fill_naturals(x)
        return n(x)
    raise TypeError()


def n(x):
    if x < 0:
        return -n(-x)

    ret = _n_cache.get(x)
    if ret is None:
        ret = _n_cache[x] = _n(x)
    return ret
