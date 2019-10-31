from inspect import signature, Parameter
from itertools import chain, product, permutations
from typing import Union, Callable, get_type_hints, Any, Tuple, Collection


def to_type_iter(t: Union[type, None]):
    """
    Convert a type hint to an iteration of concrete types
    :param t: the type hint
    :return: a tuple of concrete types
    can handle:
    * types
    * singletons (..., None, Notimplemented)
    * the typing.Any object (equivalent to object)
    * any non-specific typing abstract class (Sized, Iterable, ect...)
    * typing.Union
    """
    if isinstance(t, type):
        return t,
    if t is Any:
        return to_type_iter(object)
    if t in (..., NotImplemented, None):
        return to_type_iter(type(t))
    if getattr(t, '__origin__', None) is Union:
        return tuple(chain.from_iterable(to_type_iter(a) for a in t.__args__))
    if isinstance(getattr(t, '__origin__', None), type) and not t.__args__:
        return to_type_iter(t.__origin__)
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
    def from_func(cls, priority, func, fallback_type_hint=_missing):
        """
        create a list of candidates from function using the function's type hints. ignores all parameters with default
        values, as well as variadic parameters or keyword-only parameters

        :param priority: the priority of the candidate
        :param func: the function to use
        :param fallback_type_hint: the default type hint to use for parameters with missing hints
         this function

        :return: a list of candidates generated from the function
        """
        type_hints = get_type_hints(func)
        params = signature(func).parameters
        type_iters = []
        p: Parameter
        for p in params.values():
            if p.kind not in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) \
                    or p.default is not p.empty:
                break
            t = type_hints.get(p.name, fallback_type_hint)
            if t is _missing:
                raise KeyError(p.name)
            i = to_type_iter(t)
            type_iters.append(i)
        type_lists = product(*type_iters)
        return [cls(tuple(types), func, priority) for types in type_lists]

    def __str__(self):
        return (self.__name__ or 'unnamed candidate') + '<' + ', '.join(n.__name__ for n in self.types) + '>'

    def permutations(self, first_priority_offset=0.5):
        """
        create a list of candidates from a single candidate, such that they all permutations
        of the candidate's types will be accepted. Useful for symmetric functions.

        :param first_priority_offset: the priority increase to give the first output of the list,
         to avoid priority collisions

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
                priority = self.priority + first_priority_offset
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
                priority = self.priority
            ret.append(
                Candidate(t, func, priority)
            )
        return ret


def cmp_key(rhs: Tuple[type, ...], lhs: Tuple[type, ...]):
    """
    check whether two type tuples are ordered in any way
    :return: -1 if rhs is a sub-key of lhs, 1 if lhs is a sub-key of rhs, 0 if the two keys cannot be compared
     (it is an error to sent identical keys)
    """
    ret = 0
    for r, l in zip(rhs, lhs):
        if r is l:
            continue
        elif issubclass(r, l):
            if ret == 1:
                return 0
            ret = -1
        elif issubclass(l, r):
            if ret == -1:
                return 0
            ret = 1
        else:
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
