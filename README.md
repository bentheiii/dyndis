# Dyndis

[`pip install dyndis`](https://pypi.org/project/dyndis/)

## About

Dyndis is a library to easily and fluently make multiple-dispatch functions and methods. It was originally made for
operators in non-strict hierarchical systems but can also serve any other multiple-dispatch purpose.

## Simple Example

```python
from typing import Union

from dyndis import MultiDispatch


@MultiDispatch
def foo(a, b):
    # default implementation in case no candidates match
    raise TypeError


@foo.register()
def _(a: int, b: Union[int, str]):
    return "overload 1 <int, (int|str)>"


@foo.register()
def _(a: object, b: float):
    return "overload 2 <any, float>"


foo(1, "hello")  # overload 1
foo(("any", "object", "here"), 2.5)  # overload 2
foo(2, 3)  # overload 1
foo(2, 3.0)  # overload 2
```

## Features

* dynamic upcasting.
* seamless usage of type-hints and type variables.
* advanced data structures to minimize candidate lookup time.
* implementor interface makes it easy to create method-like overloads

## How Does it Work?

The central class (and only one users need to import) is `MultiDispatch`. `MultiDispatch` contains candidate
implementations sorted by both priority and types of the parameters they accept. When the `MultiDispatch` is called, it
calls its relevant candidates (ordered by both priority, inheritance, and compatibility, expanded upon below) until one
returns a non-`NotImplemented` return value.

## The Lookup Order

All candidates for parameters of types <T0, T1, T2..., TN> are ordered as follows:

* Any candidate with a types that is incompatible with any type in the key is excluded. That is, if for any 0 <= `i` <=
  N, a candidate's type constraint for parameter `i` is not a superclass of Ti, the candidate is excluded.
* Candidates are ordered by inheritance. A candidate is considered to inherit another candidate if all its parameter
  types are subclasses of (or are likewise covered by) the other's respective parameter type. A candidate will be
  considered before any other candidate it inherits. So for example, <int,object> will be considered before <Number,
  object>.

If there are two candidates that do not inherit each other, an exception (of type `dyndis.AmbiguityError`) is raised (
unless a candidate with greater precedence than both succeeds first).

If a candidate returns `NotImplemented`, the next candidate in the order is tried. If no candidates are accepted or all
candidates returned `NotImplemented`, the default implementation is called.

## Topology and Caches

`dyndis` uses a topological set to order all its candidates by the parameter types, so that most of the candidates can
be disregarded without any overhead.

Considering all these candidates for every lookup gets quite slow and encumbering very quickly. For this reason,
every `MultiDispatch` automatically caches these computation for both sorting and processing candidates.

## Default, Variadic, and Keyword parameters

* If a candidate has positional parameters with a default value and a type annotation, the default value will be ignored
  for the purposes of candidate resolution.
* If a candidate has a variadic positional parameter, it is ignored. When called from a `MultiDispatch`, its value will
  always be `()`.
* If a candidate has keyword-only parameters, the parameter will not be considered for candidate types, it must either
  have a default value or be set when the `MultiDispatch` is called.
* If a candidate has a variadic keyword parameter, it is ignored. When called from a `MultiDispatch`, its value will be
  according to the (type-ignored) keyword arguments.

In general, when a `MultiDispatch` is called with keyword arguments, those arguments are not considered for candidate
resolution and are sent to each attempted candidate as-is.

## Implementors

an `Implementor` is a descriptor that makes it easy to create method-like candidates inside classes.

```python
from dyndis import MultiDispatch


@MultiDispatch
def add(self, other):
    return NotImplemented


class Base:
    __add__ = add


class A(Base):
    @add.implement(__qualname__)
    def add(self, other: 'A'):
        # in implementor methods, `self` is assumed to be of the owner class
        return "A+A"

    @add.implement(__qualname__)
    def add(self, other: Base):
        return "A+Base"


class B(Base):
    @add.implement(__qualname__)
    def add(self, other: A):
        return 'B+A'


a = A()
b = B()
base = Base()
a + b  # A+B
a + base  # A+Base
a + a  # A+A
```

## Special Type Annotations

type annotations can be of any type, or among any of these special values

* `typing.Union`: accepts parameters of any of the enclosed type
* `typing.Optional`: accepts the enclosed type or `None`
* `typing.Any`: is considered a supertype for any type, including `object`
* Any of typing's aliases and abstract classes such as `typing.List` or `typing.Sized`: equivalent to their origin
  type (note that specialized aliases such as `typing.List[str]` are invalid)
* `typing.TypeVar`: see below
* `None`, `...`, `NotImplemented`: equivalent to their types

## `TypeVar` annotations

Parameters can also be annotated with `typing.TypeVar`s. These variables bind greedily as they are encountered, and
count as matched upon first binding. After first binding, they are treated as the bound type (or the lowest constraint
of the `TypeVar`) for all respects.

```python
from typing import TypeVar, Any

from dyndis import MultiDispatch

T = TypeVar('T')


@MultiDispatch
def foo(*args):
    raise TypeError


@foo.register()
def _(a: T, b: T):
    return "type(b) <= type(a)"


@foo.register()
def _(a: Any, b: Any):
    return "type(b) </= type(a"


foo(1, 1)  # <=
foo(1, True)  # <=
foo(2, 'a')  # </=
foo(object(), object())  # <=
# type variables bind greedily, meaning their exact value will be equal to the first type they encounter
foo(False, 2)  # </=
```
