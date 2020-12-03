from abc import abstractmethod
from itertools import chain, product
from typing import TypeVar, Dict, MutableSet, Callable

from dyndis.type_keys.type_key import CoreTypeKey, ClassKey, type_key, within_constraints


class UnboundDelegate(CoreTypeKey):
    """
    A delegate for an assigned TypeVar
    """

    class Nil:
        """
        A class that cannot be instantiated, useful for silently failing an unbound delegate
        """

        def __new__(cls):
            raise TypeError('cannot instantiate instance of class Nil')

        def __init_subclass__(cls, **kwargs):
            raise TypeError('cannot subclass Nil')

    def __init__(self, *type_vars: TypeVar):
        """
        :param type_var: the type variable to use
        """
        self.type_vars = type_vars
        self._possibilities = ...

    @abstractmethod
    def __call__(self, *bound_types: type) -> type:
        """
        resolve the delegate

        :param bound_type: the assigned type of the type variable
        :return: the type to delegate to
        """
        return self.Nil

    def get(self, defined_type_var: Dict[TypeVar, ClassKey]):
        defs = [defined_type_var.get(tv) for tv in self.type_vars]
        if None in defs:
            raise UnboundTypeVarError(self, [tv for (tv, b) in zip(self.type_vars, defs) if b is None])
        return type_key(
            self(*(d.inner for d in defs))
        )

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]):
        return self.get(defined_type_var).match(query_key, defined_type_var)

    def possibilities(self):
        """
        :return: all possible values of the delegate, or None if it cannot be calculated
        Node: can only be calculated if all typevars are constrained
        """
        if self._possibilities is ...:
            constraints = []
            for t in self.type_vars:
                if not t.__constraints__:
                    self._possibilities = None
                    break
                constraints.append(t.__constraints__)
            else:
                self._possibilities = tuple(
                    self(*args) for args in product(*constraints)
                )
        return self._possibilities

    def __lt__(self, other):
        pos = self.possibilities()
        if pos is None:
            return NotImplemented
        return within_constraints(pos, other, True)

    def __le__(self, other):
        if self == other:
            return True
        pos = self.possibilities()
        if pos is None:
            return NotImplemented
        return within_constraints(pos, other, False)

    def introduce(self, encountered_type_variables: MutableSet[TypeVar]):
        super().introduce(encountered_type_variables)
        missing = [tv for tv in self.type_vars if tv not in encountered_type_variables]
        if missing:
            raise OrphanDelegateError(self, missing)


_raise = object()


class UnboundAttr(UnboundDelegate):
    """
    A delegate that gets an attribute of a type
    """

    def __init__(self, type_var: TypeVar, attribute: str, default=_raise):
        """
        :param attribute: the attribute name to extract
        :param default: the default value to return if the attribute does not exist, if none is entered, and exception
         will be raised instead.
        """
        super().__init__(type_var)
        self.attribute = attribute
        self.default = default

    def __call__(self, bound_type: type):
        ret = getattr(bound_type, self.attribute, self.default)
        if ret is _raise:
            raise AttributeError(self.attribute)
        return ret

    def __eq__(self, other):
        return type(self) == type(other) and \
               (self.type_vars, self.attribute, self.default) == (other.type_var, other.attribute, other.default)

    def __hash__(self):
        return hash((self.type_vars, self.attribute, self.default))

    def __repr__(self):
        if self.default is _raise:
            return f'{type(self).__name__}({self.type_vars[0].__name__}, {self.attribute!r})'
        return f'{type(self).__name__}({self.type_vars[0].__name__}, {self.attribute!r}, {self.default!r})'


class UnboundMap(UnboundDelegate):
    """
    A delegate that calls a function
    """

    def __init__(self, func: Callable[..., type], *type_vars):
        super().__init__(type_vars)
        self.func = func

    def __call__(self, *bound_types: type):
        return self.func(*bound_types)

    def __eq__(self, other):
        return type(self) == type(other) and \
               (self.type_vars, self.func) == (other.type_var, other.func)

    def __hash__(self):
        return hash((self.type_vars, self.func))

    def __repr__(self):
        return f'{type(self).__name__}(' \
               + ", ".join(chain((repr(self.func),), *(t.__name___ for t in self.type_vars))) \
               + ')'


class UnboundTypeVarError(RuntimeError):
    """An error indicating that an UnboundDelegate resolution was attempted when the original type var was not
     assigned, in theory this exception should never be raised, since OrphanDelegateError should be raised at
      function definition."""

    def __init__(self, unbound_delegate, unbound_vars):
        super().__init__(f'type variable {unbound_vars} must be bound before {unbound_delegate}')


class OrphanDelegateError(TypeError):
    """An error indicating that an UnboundDelegate was used as a type hint before its associated typevar"""

    def __init__(self, unbound_delegate, not_defined):
        super().__init__(f'type variable {not_defined} must be used as a type hint before {unbound_delegate}')
