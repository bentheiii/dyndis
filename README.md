# Dyndis

## About
Dyndis is a library to easily and fluently make multiple-dispatch functions and methods. It was originally made for operators in non-strict hierarchical systems but can also serve any other multiple-dispatch purpose.
## Simple Example
```python
from typing import Union

from dyndis import MultiDispatch
foo = MultiDispatch()
@foo.add_func()
def foo(a: int, b: Union[int, str]):
    return "overload 1 <int, (int, str)>"
@foo.add_func()
def foo(a: object, b: float):
    return "overload 2 <any, float>"

foo(1, "hello")  # overload 1
foo(("any", "object", "here"), 2.5)  # overload 2
foo(2, 3)  # overload 1
foo(2, 3.0)  # overload 2
```
## Features
* dynamic upcasting
* customizable priorities for candidates
* seamless usage of type-hints
* type-trie to minimize candidate lookup time
* powerful caching of candidates by layer to minimize lookup time for repeat parameters without iterating through all candidates unnecessarily.
* implementor interface makes it easy to create method-like overloads
## How Does it Work?
The central class (and only one users need to import) is `MultiDispatch`. `MultiDispatch` contains candidate implementations sorted by both priority and types of the parameters they accept. When the `MultiDispatch` is called, it calls its relevant candidates (ordered by both priority and compatibility, expanded upon below) until one returns a non-NotImplement return value.
## The Lookup Order
All candidates for parameters of types <T0, T1, T2..., TN> are ordered as follows:
 * Any candidate with a types that is incompatible with any type in the key is excluded. That is, if for any 0 <= `i` <= N, a candidate's type constraint for parameter `i` is not a superclass of Ti, the candidate is excluded.
 * Candidates are ordered (ascending) by how many upcasts are required for the key type to match the candidate types (this is called their rank). So for example, for a type key <int, tuple, string>, the following candidates will be ordered as follows:
    1. <int, tuple, string>, since it requires 0 upcasts
    1. <int, Iterable, string> since it requires 1 upcasts
    1. <Number, tuple, Sequence>, since it requires 2 upcasts
    1. <object, Sequence, Sequence>, since it requires 3 upcasts
  
   Note that upcasting does consider how far the hierarchy the casting is, so a candidate <object, object, object> will have the same rank as <object, Sequence, Sequence> (but see below).
 * Then, all candidates of equal rank are sorted (descending) by their priority. All decorators have a parameter to set a priority for candidates, by default the priority is 0. It is recommended to use whole numbers for priority as non-whole numbers are use to internally organize candidates (such as with symmetric candidates, below).
 * Finally, of a set of candidates of equal rank and priority, if any candidate's parameter types are subclasses of all other candidates in the set, that candidate has priority. So that <int,object> will be considered before <Number, object> even for parameter type <bool, str>
 
If two candidates have equal rank and priority, and neither is a strict sub-key of the other, an exception (of type `dyndis.AmbiguityError`) is raised.
## Tries and Caches
`MultiDispatch` uses a non-compressing trie to order all its candidates by the parameter types, so that most of the candidates can be disregarded without any overhead. The trie also allows to lazily evaluate all rank 0 candidates before all rank 1, and so on.

Considering all these candidates for every lookup gets quite slow and encumbering very quickly. For this reason, every `MultiDispatch` automatically caches any work done by previous calls when it comes to sorting and processing candidates. The cache maintains the laziness of the trie, and minimizes the work done at any given time.
## Default, Variadic, and Keyword parameters
* If a candidate has positional parameters with a default value, these parameters are ignored for the purpose of the candidate's parameter types. When called from a `MultiDispatch`, the parameter's values will always be the default.
* If a candidate has a variadic positional parameter, it is ignored. When called from a `MultiDispatch`, its value will always be `()`.
* If a candidate has keyword-only parameters, the parameter will not be considered for candidate types, it must either have a default value or be set when the `MultiDispatch` is called.
* If a candidate has a variadic keyword parameter, it is ignored. When called from a `MultiDispatch`, its value will be according to the (type-ignored) keyword arguments.

In general, when a `MultiDispatch` is called with keyword arguments, those arguments are not considered for candidate resolution and are sent to each attempted candidate as-is.
## Implementors
an `Implementor` is a descriptor that makes it easy to create method-like candidates inside classes.
```python
from dyndis import MultiDispatch

add = MultiDispatch()
class Base:
    __add__ = add.op  # MultiDispatch.op returns a delegate descriptor that acts as an operator

class A(Base):
    @add.implementor()
    def add(self, other):
        # in implementor methods, any parameter without a type hint is assumed to be of the owner class
        return "A+A"
    @add.implementor()
    def add(self, other: Base):
        return "A+Base"

class B(Base):
    @add.implementor()
    def add(self, other: A):
        return 'B+A'
    @add.implementor()
    def add(other: A, self):
        # this isn't pretty, we'll see how to circumvent this later
        return 'A+B'

a = A()
b = B()
base = Base()
a + b  # A+B
a + base  # A+Base
a + a  # A+A
b + a  # B+A
```

In addition, implementor methods can also use the `Self` object to represent the containing class in more powerful manners.

```python
from typing import Union
from dyndis import Self, MultiDispatch

foo = MultiDispatch('foo')

class A:
    @foo.implementor()
    def foo(self, other: bool):
        return "bool"
    @foo.implementor()
    def foo(self, other: Union[Self, str]):
        return "A or str"

a = A()
a.foo(False)  # "bool"
a.foo(a)  # "A or str"
```

## Symmetric Candidates
In some cases, we will have multiple candidates that only differ by the order of the parameters (for example, addition is usually symmetrical). For this, we can make use of the `symmetric` parameter available both in `add_func` and `implementor` methods. Setting this parameter to `True` will also add virtual candidates of all the permutations of the argument types.
```python
from dyndis import MultiDispatch

add = MultiDispatch()
class Base:
    __add__ = add.op  # MultiDispatch.op returns a delegate descriptor that acts as an operator

class A(Base):
    ...

class B(Base):
    @add.implementor(symmetric = True)
    def add(self, other: A):
        return 'A+B/B+A'

a = A()
b = B()
a + b  # A+B/B+A
b + a  # A+B/B+A
```
In any symmetric candidate set, one is given a larger priority by 0.5.

One should take take when making symmetric candidates, as it can create an inordinate number of candidates (super-exponential to the number of parameters).
## RawReturnValue
By default, if a candidate returns `NotImplemented`, it indicates to the `MultiDispatch` that the next candidate should be tried. However, on the rare occasion when `NotImplemented` is the actual return value desired, a candidate should return `dyndis.RawNotImplemented`.