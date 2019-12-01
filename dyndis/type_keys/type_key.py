from __future__ import annotations

from functools import lru_cache
from typing import Union, Dict, TypeVar, Hashable, Any, Iterable, Optional, Tuple, ByteString, Generic, MutableSet

from abc import abstractmethod, ABC
from enum import IntEnum

from dyndis.util import get_args, get_origin

try:
    from typing import Literal
except ImportError:
    Literal = None

# a special Type Variable to designate the owner class
Self = TypeVar('Self')


class MatchKind(IntEnum):
    """
    Reflects a kind of match, and by how much to increase the rank of the candidate
    """
    perfect = 0
    upcast = 1


class MatchException(RuntimeError):
    """
    An error that occurs during a match, and might be delayed until its rank is reached
    """
    rank_offset: int


class TypeKey(ABC):
    """
    A key to be used to identify a parameter
    """

    @abstractmethod
    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) \
            -> Union[MatchKind, None, MatchException]:
        """
        Evaluate the query key into the type key
        :param query_key: the type of the parameter to be matched
        :param defined_type_var: a dictionary mapping already bound type variables to their associated types
        :return: A MatchKind if there is a match, a MatchException if an error occurred, or None if there is no Match
        """
        pass

    def __call__(self):
        # typing's structures (like Union) will reject all non-callable arguments,
        # so we have to make TypeKey seem callable
        raise TypeError(f"can't call {type(self)}")

    __hash__ = None




@lru_cache
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
        if t is Self:
            return SelfKey
        return TypeVarKey(t)
    if t is Any:
        return AnyKey
    if t in (..., NotImplemented, None):
        return SingletonTypeKey(t)

    origin = get_origin(t)

    if Literal and origin is Literal:
        return LiteralTypeKey(t)
    if origin is Union:
        return UnionTypeKey(t)
    if isinstance(origin, type) and is_type_like(t):
        return type_key(origin)
    raise TypeError(f'type annotation {t} is not a type, give it a default to ignore it from the candidate list')


@lru_cache
def type_keys(t) -> Tuple[Union[CoreTypeKey, SelfKeyCls]]:
    """
    Convert a type hint to an iteration of core type keys (or SelfKey)
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

    def priority_offset(self):
        """
        :return: a number to add to the priority of a candidate
        note that for each candidate, this method will only be called once, even if the type key is used multiple times
        """
        return 0

    def is_simple(self):
        """
        for a simple type key K, for any class c:
        * K.match(c) == MatchKind.perfect iff K == c
        * K.match(c) == MatchKind.upcast iff K != c and K in c.__mro__
        * K.match(c) is None otherwise
        """
        return False

    @abstractmethod
    def __le__(self, other: CoreTypeKey):
        """
        A <= B if for every class c that A matches:
        * B also matches c
        * B.match(c) >= A.match(c)
        """
        pass

    @abstractmethod
    def __lt__(self, other: CoreTypeKey):
        """
        A < B if A <= B and also there exists class c that B matches s.t.:
        * A doesn't match c
        OR
        * B.match(c) > A.match(c)
        """
        pass

    @abstractmethod
    def __eq__(self, other):
        """
        used for upholding of is_simple requirement
        """
        pass

    @abstractmethod
    def __hash__(self):
        """
        used for upholding of is_simple requirement
        """
        pass

    @abstractmethod
    def __repr__(self):
        """
        Core type keys appear in candidate representations, so they must look like the annotation used ot create them
        """
        pass


class CoreWrapperKey(CoreTypeKey, WrapperKey[T], Generic[T], ABC):
    """
    A mixin type key class or core and wrapper
    """

    def __repr__(self):
        return repr(self.inner)

    def __eq__(self, other):
        return other == self.inner \
               or (type(self) == type(other) and self.inner == other.inner)

    def __hash__(self):
        return hash(self.inner)


object_subclass_check = type(object).__subclasscheck__


class ClassKey(CoreWrapperKey[type]):
    """
    A type key of a superclass
    """

    def match(self, query_key: type, defined_type_var) -> Union[MatchKind, None, Exception]:
        if query_key is self.inner:
            return MatchKind.perfect
        elif issubclass(query_key, self.inner):
            return MatchKind.upcast
        return None

    def __le__(self, other):
        if isinstance(other, ClassKey):
            return issubclass(self.inner, other.inner)
        return not (other < self)

    def __lt__(self, other):
        if isinstance(other, ClassKey):
            return self.inner != other.inner and issubclass(self.inner, other.inner)
        return not (other <= self)

    def is_simple(self):
        """
        >>> ClassKey(float).is_simple()
        True
        >>> ClassKey(int).is_simple()
        True
        >>> ClassKey(bool).is_simple()
        True
        >>> class A: pass
        >>> ClassKey(A).is_simple()
        True
        >>> from collections.abc import Iterable
        >>> ClassKey(Iterable).is_simple()
        False
        >>> from abc import ABC
        >>> class B(ABC): pass
        >>> ClassKey(B).is_simple()
        False
        """
        return type(self.inner).__subclasscheck__ is object_subclass_check

    def __repr__(self):
        return self.inner.__name__


class TypeVarKey(CoreWrapperKey[TypeVar]):
    """
    A type key of a type variable
    """

    def priority_offset(self):
        return -1

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) -> Union[MatchKind, None, Exception]:
        return defined_type_var[self.inner].match(query_key, defined_type_var)

    def __le__(self, other):
        if self == other:
            return True
        if self.inner.__constraints__:
            return all(c <= other for c in self.inner.__constraints__)
        if self.inner.__bound__ and other < type_key(self.inner.__bound__):
            return False
        return NotImplemented

    def __lt__(self, other):
        if self == other:
            return False
        if self.inner.__constraints__:
            return all(c < other for c in self.inner.__constraints__)
        if self.inner.__bound__ and other <= type_key(self.inner.__bound__):
            return False
        return NotImplemented

    def introduce(self, encountered_type_variables: MutableSet[TypeVar]):
        super().introduce(encountered_type_variables)
        encountered_type_variables.add(self.inner)


class AnyKeyCls(CoreWrapperKey[type(Any)]):
    def __init__(self):
        super().__init__(Any)

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) -> Union[MatchKind, None, Exception]:
        return MatchKind.upcast

    def __le__(self, other):
        return other is self

    def __lt__(self, other):
        return False


AnyKey = AnyKeyCls()


# endregion


# region splitters
class SplittingTypeKey(TypeKey):
    """
    A splitting type key is one that can be split into core type keys. splitting type keys are
     unhashable to ensure they don't end up in the candidate trie. Splitting TypeKeys are supposed to be short lived,
     either as intermediary steps while evaluating annotations or as values returned by delegates.
    """

    @abstractmethod
    def split(self) -> Iterable[Union[SplittingTypeKey, CoreTypeKey]]:
        """
        split the type key into smaller (possibly core) type keys
        """
        pass

    def match(self, query_key: type, defined_type_var: Dict[TypeVar, ClassKey]) \
            -> Union[MatchKind, None, MatchException]:
        ret = None
        for s in self.split():
            r = s.match(query_key, defined_type_var)
            if r is None:
                continue
            if isinstance(r, MatchException):
                return r
            if ret is None or ret > r:
                ret = r
        return ret

    __hash__ = None


class SplittingClassTypeKey(WrapperKey[type], SplittingTypeKey):
    """
    A class type key for classes that, according to various PEPs, should be treated as unions
    """
    TYPE_ALIASES: Dict[type, Tuple[type, ...]] = {
        float: (float, int),
        complex: (float, int, complex),
        bytes: (ByteString,)
    }

    def __init__(self, inner):
        super().__init__(inner)
        self.aliases = self.TYPE_ALIASES[inner]

    def split(self) -> Optional[Iterable[TypeKey]]:
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


if Literal:
    class LiteralTypeKey(WrapperKey, SplittingTypeKey):
        """
        A type key for literal types
        """

        def __init__(self, inner):
            if set(get_args(inner)) <= frozenset((..., NotImplemented, None)):
                raise TypeError('cannot have non-singleton in literal key')
            super().__init__(inner)

        def split(self) -> Iterable[TypeKey]:
            return (type_key(a) for a in get_args(self.inner))


# endregion

class SelfKeyCls(TypeVarKey):
    """
    A special type key that evaluates to the candidate's self_type when the candidate is created
    """
    __hash__ = None


SelfKey = SelfKeyCls(Self)
