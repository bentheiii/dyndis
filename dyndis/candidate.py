from inspect import signature, Parameter
from itertools import chain, product, permutations
from numbers import Number
from typing import Union, Callable, get_type_hints, Optional

Priority = Number


def to_type_iter(t):
    if isinstance(t, type):
        return t,
    if getattr(t, '__origin__', None) is Union:
        return tuple(chain.from_iterable(to_type_iter(a) for a in t.__args__))
    if isinstance(getattr(t, '__origin__', None), type) and not t.__args__:
        return to_type_iter(t.__origin__)
    raise TypeError(f'type annotation {t} is not a type, give it a default to ignore it from the candidate list')


class Candidate:
    def __init__(self, types, func: Callable, priority):
        self.types = types
        self.func = func
        self.priority = priority

    @classmethod
    def from_func(cls, priority, func, default_type_hints=None, fallback_type_hint=None):
        if default_type_hints:
            type_hints = default_type_hints
        else:
            type_hints = {}
        type_hints.update(get_type_hints(func))
        params = signature(func).parameters
        type_iters = []
        p: Parameter
        for p in params.values():
            if p.kind not in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) \
                    or p.default is not p.empty:
                break
            t = type_hints.get(p.name, fallback_type_hint)
            if t is None:
                raise KeyError(p.name)
            i = to_type_iter(t)
            type_iters.append(i)
        type_lists = product(*type_iters)
        return [cls(tuple(types), func, priority) for types in type_lists]

    def __str__(self):
        return (self.__name__ or 'unnamed candidate') + '<' + ', '.join(
            n.__name__ for n in self.types) + '>'

    def permutations(self, first_priority_offset=0.5):
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
                exec(f"def func({args}): return __original__({call_args})",
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

    @property
    def __name__(self) -> Optional[str]:
        return getattr(self.func, '__name__', None)

    @property
    def __doc__(self) -> Optional[str]:
        return getattr(self.func, '__doc__', None)
