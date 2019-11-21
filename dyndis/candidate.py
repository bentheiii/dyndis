from inspect import signature, Parameter
from itertools import chain, product, permutations
from typing import Union, Callable, get_type_hints, Any, Tuple, Collection, TypeVar, Dict, Type, Optional, ByteString
from warnings import warn

from dyndis.util import similar, issubclass_tv, SubPriority, get_origin, get_args, cmp_type_hint

try:
    from typing import Literal
except ImportError:
    Literal = None

Self = TypeVar('Self')

type_aliases: Dict[type, Tuple[type, ...]] = {
    float: (float, int),
    complex: (float, int, complex),
    bytes: (ByteString,)
}


def to_type_iter(t: Union[type, None], self_type):
    """
    Convert a type hint to an iteration of concrete types
    :param t: the type hint
    :param self_type: the type to substitute when encountering Self
    :return: a tuple of concrete types
    can handle:
    * types
    * singletons (..., None, Notimplemented)
    * the typing.Any object (equivalent to object)
    * the dyndis.Self object
    * any non-specific typing abstract class (Sized, Iterable, ect...)
    * Type variables
    * typing.Union
    3.8 only:
    * Literals of singleton types
    """
    if isinstance(t, type):
        alias = type_aliases.get(t, None)
        return alias or (t,)
    if t is Any:
        return t,
    if t is Self:
        if self_type is _missing:
            raise ValueError('Self cannot be used as a type hint outside of Implementor')
        return to_type_iter(self_type, self_type)
    if t in (..., NotImplemented, None):
        return to_type_iter(type(t), self_type)
    if isinstance(t, TypeVar):
        if t.__contravariant__ or t.__covariant__:
            raise ValueError(f'cannot use covariant or contravariant type hint {t}')
        return t,

    origin = get_origin(t)
    args = get_args(t)

    if Literal and origin is Literal:
        if any(a not in (None, ..., NotImplemented) for a in args):
            raise TypeError('only Literal[singleton] can be used in type hint')
        return chain.from_iterable(to_type_iter(a, self_type) for a in args)
    if origin is Union:
        return chain.from_iterable(to_type_iter(a, self_type) for a in t.__args__)
    if isinstance(origin, type) and not args:
        return to_type_iter(origin, self_type)
    raise TypeError(f'type annotation {t} is not a type, give it a default to ignore it from the candidate list')


_missing = object()


class Candidate:
    """
    A class representing a specific implementation for a multi-dispatch
    """

    def __init__(self, types, func: Callable, priority):
        """
        :param types: the types for the conditions
        :param func: the function of the implementation
        :param priority: the priority of the candidate over other candidates (higher is tried first)
        """
        self.types = types
        self.func = func
        self.priority = priority
        self.__name__ = getattr(func, '__name__', None)
        self.__doc__ = getattr(func, '__doc__', None)

    @classmethod
    def from_func(cls, priority, func, fallback_type_hint=_missing, self_type=_missing,
                  priority_adjust: Optional[Callable] = ...):
        """
        create a list of candidates from function using the function's type hints. ignores all parameters with default
        values, as well as variadic parameters or keyword-only parameters

        :param priority: the priority of the candidate
        :param func: the function to use
        :param fallback_type_hint: the default type hint to use for parameters with missing hints
         this function

        :return: a list of candidates generated from the function
        """
        if priority_adjust is ...:
            def priority_adjust(original, types):
                # reduce the priority by the number of distinct type variables
                t_var_count = len(set(t for t in types if isinstance(t, TypeVar)))
                original = SubPriority.make(original, -t_var_count)
                return original
        if priority_adjust is None:
            def priority_adjust(original, types):
                return original

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
            i = to_type_iter(t, self_type)
            if p.default is not p.empty:
                default_type = type(p.default)
                if default_type is not object \
                        and not any(issubclass_tv(default_type, x) for x in i):
                    if p.default is None:
                        i = (default_type, *i)
                    else:
                        warn(f'default value for parameter {p.name} is not included in its annotations', stacklevel=3)
                super_type_iters.append(list(type_iters))
            type_iters.append(i)

        type_lists = list(chain.from_iterable(product(*ti) for ti in super_type_iters))
        return [cls(tuple(types), func,
                    priority_adjust(priority, tuple(types))
                    ) for types in type_lists]

    def __str__(self):
        return (self.__name__ or 'unnamed candidate') + '<' + ', '.join(n.__name__ for n in self.types) + '>'

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
                if t in seen:
                    continue
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
                priority = SubPriority.make(self.priority)
            ret.append(
                Candidate(t, func, priority)
            )
        return ret


def cmp_key(rhs: Tuple[type, ...], lhs: Tuple[type, ...]):
    """
    check whether two type tuples are ordered in any way
    :return: -1 if rhs is a sub-key of lhs, 1 if lhs is a sub-key of rhs, 0 if the two keys cannot be compared
     (it is an error to send identical keys)
    """
    ret = 0
    for r, l in zip(rhs, lhs):
        i = cmp_type_hint(r, l)
        if i is None:
            return 0
        if i == 0:
            continue

        if ret == 0:
            ret = i
        elif ret != i:
            return 0
    return ret


def get_least_key_index(candidates: Collection[Candidate]):
    """
    :param candidates: a collection of candidates
    :return: the index of the candidate with a least-key from among the candidates, or -1 if none exists
    """
    # todo test
    if len(candidates) < 2:
        return -1
    i = iter(candidates)
    ret = next(i)
    ret_ind = 0
    for ind, k in enumerate(i, 1):
        cmp = cmp_key(ret.types, k.types)
        if cmp == 0:
            return -1
        if cmp == 1:
            ret_ind = ind
            ret = k
    return ret_ind
