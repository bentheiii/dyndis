from __future__ import annotations

from functools import lru_cache
from typing import Union, Dict, Hashable, Any, Iterable, Optional, Tuple, ByteString, Generic, MutableSet, TypeVar,\
    Iterator
from abc import abstractmethod, ABC

from dyndis.util import get_args, get_origin, liberal_cache


class MatchException(RuntimeError):
    """
    An error that occurs during a match, and might be delayed until its rank is reached
    """


class AmbiguousBindingError(MatchException):
    """An error indicating that a type variable could not find a single type to bind to"""

    def __init__(self, typevar, subclass, unrelated_classes):
        super().__init__(f'type variable {typevar} must up-cast type {subclass} to one of its constrained types,'
                         f' but it is a subclass of multiple non-related constraints: {unrelated_classes}'
                         f' (consider adding {subclass} as an explicit constraint in {typevar},'
                         f' or a specialized overload for {subclass})')


class TypeLikeMixin:
    def __call__(self):
        # typing's structures (like Union) will reject all non-callable arguments,
        # so we have to make TypeKey seem callable
        raise TypeError(f"can't call {type(self)}")  # pragma: no cover


class TypeKey(ABC):
    """
    A key to be used to identify a parameter
    """

    @abstractmethod
    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) \
            -> Union[bool, MatchException]:
        """
        Evaluate the query key into the type key
        :param query_key: the type of the parameter to be matched
        :param defined_type_var: a dictionary mapping already bound type variables to their associated types
        :return: Whether there is a match, or a MatchException if an error occurred
        """
        pass

    @abstractmethod
    def __le__(self, other: CoreTypeKey):
        """
        A <= B if for every class c that A matches, B also matches c
        """
        pass

    @abstractmethod
    def __lt__(self, other: CoreTypeKey):
        """
        A < B if A <= B and also there exists class c that B matches s.t. A doesn't match c
        """
        pass


@liberal_cache
def type_key(t) -> TypeKey:
    """
    convert type annotation in a (possibly non-core) type key
    """

    def is_type_like(ga):
        # the best way I know of to check whether a generic alias is usable as class
        try:
            isinstance(None, ga)
        except TypeError:
            return False
        return True

    if isinstance(t, TypeKey):
        return t
    if isinstance(t, type):
        if t in SplittingClassTypeKey.TYPE_ALIASES:
            return SplittingClassTypeKey(t)
        return ClassKey(t)
    if isinstance(t, TypeVar):
        return TypeVarKey(t)
    if t is Any:
        return AnyKey
    if t in (..., NotImplemented, None):
        return SingletonTypeKey(t)

    origin = get_origin(t)
    if origin is Union:
        return UnionTypeKey(t)
    if isinstance(origin, type) and is_type_like(t):
        return type_key(origin)
    raise TypeError(f'type annotation {t} is not a type, give it a default to ignore it from the candidate list')


def class_type_key(t) -> ClassKey:
    """
    :return: convert the argument into a ClassTypeKey, useful for when we would like to avoid splitting type keys
    """
    tk = type_key(t)
    # special case for splitting class types
    if isinstance(tk, SplittingClassTypeKey):
        tk = next(tk.split()),
    else:
        tk = type_keys(tk)
    if len(tk) != 1 or not isinstance(tk[0], ClassKey):
        raise Exception(f'type annotation {t} must evaluate to a single type')

    return tk[0]


@liberal_cache
def type_keys(t) -> Tuple[Union[CoreTypeKey, SelfKeyCls]]:
    """
    Convert a type hint to a tuple of core type keys (or SelfKey)
    :param t: the type hint
    :return: a tuple of core or self type keys
    can handle:
    * types
    * singletons (..., None, Notimplemented)
    * the typing.Any object
    * the dyndis.Self object
    * any non-specific typing abstract class (Sized, Iterable, ect...)
    * Type variables
    * typing.Union
    * dyndis.UnboundDelegate object
    * Any TypeKey object
    3.8 only:
    * Literals of singleton types
    """

    def recursive_split(tk: TypeKey) -> Iterable[Union[CoreTypeKey, SelfKeyCls]]:
        if isinstance(tk, SplittingTypeKey):
            for t in tk.split():
                yield from recursive_split(t)
        else:
            assert isinstance(tk, (CoreTypeKey, SelfKeyCls))
            yield tk

    tk = type_key(t)
    return tuple(recursive_split(tk))


T = TypeVar('T', bound=Hashable)


class WrapperKey(TypeKey, Generic[T], ABC):
    """
    A mixin class for a type key that simply wraps a another value
    """

    def __init__(self, inner: T):
        self.inner = inner


# region core
class CoreTypeKey(TypeKey):
    """
    A core type key is one that be hashed into a dict (specifically a trie), it usually has the same hash as a
     wrapped value
    """

    def introduce(self, encountered_type_variables: MutableSet[TypeVar]):
        """
        called when the type_key is being used to construct a candidate
        :param encountered_type_variables: the type variables previously encountered in previous parameters
        """
        pass

    @abstractmethod
    def __repr__(self):
        """
        Core type keys appear in candidate representations, so they must look like the annotation used ot create them
        """
        pass


class CoreWrapperKey(WrapperKey[T], CoreTypeKey, Generic[T], ABC):
    """
    A mixin type key class or core and wrapper
    """

    def __repr__(self):
        return repr(self.inner)


def within_constraints(constraints, other, strict):
    """
    :param constraints: the constraints to compare
    :param other: the other element to use
    :param strict: if set to True, will compare for strict matches, otherwise, will compare for equal-or-less
    :return: whether all constraints are either less than or not comparable
    """
    ret = NotImplemented
    for c in constraints:
        try:
            ctk = type_key(c)
            cmp = ctk < other if strict else ctk <= other
            rev_cmp = other <= other if strict else other < ctk
        except TypeError:
            continue
        if cmp:
            if ret is False:
                return NotImplemented
            ret = True
        elif rev_cmp:
            if ret is True:
                return NotImplemented
            ret = False
    return ret


class ClassKey(CoreWrapperKey[type]):
    """
    A type key of a superclass
    """

    def match(self, query_key: type, defined_type_var) -> Union[bool, Exception]:
        return issubclass(query_key, self.inner)

    def __le__(self, other):
        if isinstance(other, ClassKey):
            if issubclass(self.inner, other.inner):
                return True
            if issubclass(other.inner, self.inner):
                return False
            return NotImplemented
        try:
            rev_cmp = other < self
        except TypeError:
            return NotImplemented
        return not rev_cmp

    def __lt__(self, other):
        if isinstance(other, ClassKey):
            if self.inner == other.inner or issubclass(other.inner, self.inner):
                return False
            if issubclass(self.inner, other.inner):
                return True
            return NotImplemented
        try:
            rev_cmp = other < self
        except TypeError:
            return NotImplemented
        return not rev_cmp

    def __repr__(self):
        return self.inner.__name__


class TypeVarKey(CoreWrapperKey[TypeVar]):
    """
    A type key of a type variable
    """

    @staticmethod
    @lru_cache()
    def constrain_type(cls, scls: Union[type, TypeVar]) -> Optional[ClassKey]:
        """
        get the lowest type that cls can be up-cast to and scls accepts as constraint. Or None if none exists.
        """
        if isinstance(scls, TypeVar):
            if scls.__constraints__:
                candidates = [c for c in scls.__constraints__ if issubclass(cls, c)]
                if not candidates:
                    return None
                minimal_candidates = [
                    cand for cand in candidates if all(issubclass(cand, c) for c in candidates)
                ]
                if len(minimal_candidates) != 1:
                    raise AmbiguousBindingError(scls, cls, minimal_candidates or candidates)
                return class_type_key(minimal_candidates[0])
            elif scls.__bound__:
                return TypeVarKey.constrain_type(cls, scls.__bound__)
            return class_type_key(cls)
        return class_type_key(cls) if issubclass(cls, scls) else None

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) -> Union[bool, MatchException]:
        return defined_type_var[self.inner].match(query_key, defined_type_var)

    def __le__(self, other):
        if self == other:
            return True

        if self.inner.__constraints__:
            return within_constraints(self.inner.__constraints__, other, strict=True)
        if isinstance(other, ClassKey):
            return class_type_key(self.inner.__bound__ or object) <= other
        return NotImplemented

    def __lt__(self, other):
        if self == other:
            return False

        if self.inner.__constraints__:
            return within_constraints(self.inner.__constraints__, other, strict=True)
        if isinstance(other, ClassKey):
            return class_type_key(self.inner.__bound__ or object) <= other
        return NotImplemented

    def introduce(self, encountered_type_variables: MutableSet[TypeVar]):
        super().introduce(encountered_type_variables)
        encountered_type_variables.add(self.inner)


class AnyKeyCls(CoreWrapperKey[type(Any)]):
    """
    A singleton type key for the Any object, that encompasses all other keys
    """

    def __init__(self):
        super().__init__(Any)

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) -> Union[bool, Exception]:
        return True

    def __le__(self, other):
        return other is self

    def __lt__(self, other):
        return False

    def __ge__(self, other):
        return True

    def __gt__(self, other):
        return other is not self


AnyKey = AnyKeyCls()


# endregion


# region splitters
class SplittingTypeKey(TypeKey):
    """
    A splitting type key is one that can be split into core type keys. splitting type keys are
     unhashable to ensure they don't end up in the candidate structure.
    """

    @abstractmethod
    def split(self) -> Iterable[Union[SplittingTypeKey, CoreTypeKey]]:
        """
        split the type key into smaller (possibly core) type keys
        """
        pass

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) \
            -> Union[bool, MatchException]:
        for s in self.split():
            r = s.match(query_key, defined_type_var)
            if r:
                return r
        return False

    def __lt__(self, other):
        split = list(self.split())
        if within_constraints(split, other, True):
            return True
        if any(other <= s for s in split):
            return False
        return NotImplemented

    def __le__(self, other):
        split = self.split()
        if within_constraints(split, other, False):
            return True
        if any(other < s for s in split):
            return False
        return NotImplemented

    __hash__ = None


class SplittingClassTypeKey(WrapperKey[type], SplittingTypeKey):
    """
    A class type key for classes that, according to various PEPs, should be treated as unions
    """
    TYPE_ALIASES: Dict[type, Tuple[type, ...]] = {
        float: (float, int),
        complex: (float, int, complex),
        bytes: (ByteString.__origin__,)
    }

    def __init__(self, inner):
        super().__init__(inner)
        self.aliases = self.TYPE_ALIASES[inner]

    def split(self) -> Optional[Iterator[TypeKey]]:
        return (ClassKey(a) for a in self.aliases)


class SingletonTypeKey(WrapperKey[Union[None, type(NotImplemented), type(...)]], SplittingTypeKey):
    """
    A type key for singleton types
    """

    def __init__(self, inner):
        if inner not in (..., NotImplemented, None):
            raise TypeError('cannot have non-singleton in singleton key')
        super().__init__(inner)

    def split(self) -> Optional[Iterable[TypeKey]]:
        return type_key(type(self.inner)),


class UnionTypeKey(SplittingTypeKey, WrapperKey):
    """
    A type key for union types
    """

    def split(self) -> Iterable[TypeKey]:
        return (type_key(a) for a in get_args(self.inner))


# endregion

class SelfKeyCls(TypeKey, TypeLikeMixin):
    """
    A special type key that evaluates to the candidate's self_type when the candidate is created
    """

    def raise_(self, *args, **kwargs):
        raise TypeError('Self is a special type kay that must not actually be used')

    match = __le__ = __lt__ = raise_


Self = SelfKeyCls()
