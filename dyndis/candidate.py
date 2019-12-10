from functools import lru_cache
from inspect import signature, Parameter
from itertools import chain, product, permutations
from typing import Callable, get_type_hints, Iterable, Tuple, Union, TypeVar, Optional
from warnings import warn

from dyndis.type_keys.type_key import TypeKey, type_keys, CoreTypeKey, Self, MatchException, TypeVarKey, ClassKey, \
    AmbiguousBindingError, class_type_key
from dyndis.util import SubPriority

try:
    from typing import Literal
except ImportError:
    Literal = None


def includes_keys(lhs: Tuple[TypeKey, ...], rhs: Tuple[TypeKey, ...]):
    """
    :return: whether each typekey in lhs is less than or equal to at least one type key in rhs
    """
    for left in lhs:
        for right in rhs:
            try:
                if left <= right:
                    break
            except TypeError:
                continue
        else:
            return False
    return True


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
            return constrain_type(cls, scls.__bound__)
        return class_type_key(cls)
    return class_type_key(cls) if issubclass(cls, scls) else None


_missing = object()


class Candidate:
    """
    A class representing a specific implementation for a multi-dispatch
    """

    def __init__(self, types: Iterable[CoreTypeKey], func: Callable, priority):
        """
        :param types: the types for the conditions
        :param func: the function of the implementation
        :param priority: the priority of the candidate over other candidates (higher is tried first)
        """
        self.types = tuple(types)
        self.func = func
        self.priority = priority
        self.__name__ = getattr(func, '__name__', None)
        self.__doc__ = getattr(func, '__doc__', None)

    @classmethod
    def from_func(cls, priority, func, fallback_type_hint=_missing, self_type=_missing):
        """
        create a list of candidates from function using the function's type hints. ignores all parameters with default
        values, as well as variadic parameters or keyword-only parameters

        :param priority: the priority of the candidate
        :param func: the function to use
        :param fallback_type_hint: the default type hint to use for parameters with missing hints
         this function
        :param self_type: the type to put in place of dyndis.Self (if found)

        :return: a list of candidates generated from the function
        """

        type_hints = get_type_hints(func)

        params = signature(func).parameters
        type_iters = []
        super_type_iters = [type_iters]
        p: Parameter
        for p in params.values():
            if p.kind not in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                break
            t = type_hints.get(p.name, fallback_type_hint)
            if t is _missing:
                if p.default is p.empty:
                    break
                raise KeyError(p.name)

            i = type_keys(t)
            if p.default is not p.empty:
                default_type = type(p.default)
                if default_type is not object:
                    default_type_keys = type_keys(default_type)
                    if not includes_keys(default_type_keys, i):
                        if p.default is None:
                            i = {*i, *default_type_keys}
                        else:
                            warn(f'default value for parameter {p.name} is not included in its annotations',
                                 stacklevel=3)
                super_type_iters.append(list(type_iters))
            type_iters.append(i)

        type_lists = chain.from_iterable(product(*ti) for ti in super_type_iters)
        ret = []
        if self_type is not _missing:
            stk = type_keys(self_type)
            if len(stk) != 1 or not isinstance(stk[0], CoreTypeKey):
                raise TypeError('self_type must evaluate to a single core type key')
            self_type_key = stk[0]
        else:
            self_type_key = None

        for types in type_lists:
            types = list(types)

            encountered_tvars = set()
            tk: TypeKey
            for i, tk in enumerate(types):
                if tk is Self:
                    if self_type_key is None:
                        raise Exception('cannot use dyndis.Self outside of implementors')
                    tk = types[i] = self_type_key
                if not isinstance(tk, CoreTypeKey):
                    raise Exception('split returned a non-core type key')
                tk.introduce(encountered_tvars)
            ret.append(cls(
                types, func,
                priority
            ))
        return ret

    def __str__(self):
        def type_name(t):
            if isinstance(t, type):
                return t.__name__
            return str(t)

        return (self.__name__ or 'unnamed candidate') + '<' + ', '.join(type_name(n) for n in self.types) + '>'

    def permutations(self):
        """
        create a list of candidates from a single candidate, such that they all permutations
        of the candidate's types will be accepted. Useful for symmetric functions.

        :return: a list of equivalent candidates, differing only by the type order
        """
        if not self.types:
            raise ValueError("can't get permutations of a 0-parameter candidate")
        ret = []
        name = getattr(self.func, '__name__', None)
        call_args = ', '.join('_' + str(i) for i in range(len(self.types)))
        seen = set()
        glob = {'__original__': self.func}
        first = True
        for perm in permutations(range(len(self.types))):
            if first:
                func = self.func
                t = self.types
                seen.add(t)
                priority = self.priority
                first = False
            else:
                t = tuple(self.types[i] for i in perm)
                if t in seen:
                    continue
                seen.add(t)

                args = ", ".join('_' + str(i) for i in perm)
                ns = {}
                exec(
                    f"def func({args}): return __original__({call_args})",
                    glob, ns
                )
                func = ns['func']
                if name:
                    func.__name__ = name
                priority = SubPriority(self.priority, -1)
            ret.append(
                Candidate(t, func, priority)
            )
        return ret

    def __lt__(self, other):
        if self.types == other.types or len(self.types) != len(other.types):
            return False
        ret = False
        for left, right in zip(self.types, other.types):
            if ret:
                try:
                    if not left <= right:
                        return False
                except TypeError:
                    return False
            else:
                try:
                    if left < right:
                        ret = True
                    elif not (left <= right):
                        return False
                except TypeError:
                    return False
        return ret

    def __le__(self, other):
        if len(self.types) != len(other.types):
            return False
        if self.types == other.types and self.priority == other.priority:
            return True
        return self < other

    def match(self, query: Tuple[type]) -> Union[bool, MatchException]:
        """
        :param query: a sequence of types to test against
        :return: whether the query types are applicable against the query, or a MatchException if one occurred
        """
        bound_tv = {}
        if len(query) != len(self.types):
            raise ValueError('length mismatch')
        for q, tk in zip(query, self.types):
            if isinstance(tk, TypeVarKey) and (tk.inner not in bound_tv):
                try:
                    constrained = constrain_type(q, tk.inner)
                except MatchException as e:
                    return e
                if not constrained:
                    return False
                bound_tv[tk.inner] = constrained
            else:
                v = tk.match(q, bound_tv)
                if not v or isinstance(v, MatchException):
                    return v
        return True
