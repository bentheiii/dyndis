from functools import partial
from typing import Dict, Tuple, Type, Any, List, Callable, Union, Iterable

from sortedcontainers import SortedDict

# todo trie for secondary candidates
from dyndis.candidate import Candidate
from dyndis.implementor import Implementor


class MultiDispatch:
    class CandidateAdderNamespace(dict):
        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        def __setitem__(self, key, value):
            if isinstance(value, staticmethod):
                value = value.__func__

            if isinstance(value, Iterable) and not isinstance(value, str):
                self.owner.add_candidates(value)

    def __init__(self, name=None, doc=None):
        self.__name__ = name
        self.__doc__ = doc

        self.candidates: Dict[Tuple[Type], SortedDict[Any, Candidate]] = {}
        self.primary_cache: Dict[Tuple[Type], List[List[Candidate]]] = {}
        self.secondary_cache: Dict[Tuple[Type], List[List[Candidate]]] = {}

    def _clean_secondary_cache(self, sizes):
        to_pop = [k for k in self.secondary_cache if len(k) in sizes]
        for tp in to_pop:
            self.secondary_cache.pop(tp)

    def _add_candidate(self, candidate: Candidate, clean_secondary_cache=True):
        sd = self.candidates.get(candidate.types)
        if sd is None:
            sd = self.candidates[candidate.types] = SortedDict()
        if candidate.priority in sd:
            raise ValueError(f'cannot insert candidate, a candidate of equal types {candidate.types}'
                             f' and priority {candidate.priority} exists ')
        sd[candidate.priority] = candidate
        self.primary_cache.pop(candidate.types, None)
        if not self.__name__:
            self.__name__ = candidate.__name__
        if not self.__doc__:
            self.__doc__ = candidate.__doc__
        if clean_secondary_cache:
            self._clean_secondary_cache((len(candidate.types),))

    def add_candidates(self, candidates):
        clean_sizes = set()
        for cand in candidates:
            self._add_candidate(cand, clean_secondary_cache=False)
            clean_sizes.add(len(cand.types))
        self._clean_secondary_cache(clean_sizes)

    def add_func(self, priority, func=None):
        if not func:
            return partial(self.add_func, priority)

        self.add_candidates(Candidate.from_func(priority, func))

    def _get_secondary_candidates(self, types):
        if types in self.secondary_cache:
            return self.secondary_cache[types]
        secondary = SortedDict()
        for k, v in self.candidates.items():
            if len(k) != len(types):
                continue
            score = 0
            for (actual_type, intended_type) in zip(types, k):
                if not issubclass(actual_type, intended_type):
                    break
                if actual_type is not intended_type:
                    score += 1
            else:
                if score == 0:
                    continue
                for c in v.values():
                    p = (score, c.priority)
                    if p not in secondary:
                        secondary[p] = [c]
                    else:
                        secondary[p].append(c)

        self.secondary_cache[types] = secondary = list(secondary.values())
        return secondary

    def _get_primary_candidates(self, types):
        if types in self.primary_cache:
            return self.primary_cache[types]

        prime = self.candidates.get(types)
        if prime:
            prime = sorted(prime.values(), key=lambda x: x.priority)
        else:
            prime = []

        self.primary_cache[types] = prime
        return prime

    def _get_candidates(self, types):
        yield from self._get_primary_candidates(types)

        secondary = self._get_secondary_candidates(types)

        for v in secondary:
            if len(v) != 1:
                raise Exception(f'multiple priority overloads: {", ".join(str(i) for i in v)}')
            yield v[0]

    def get(self, args, default=None):
        types = tuple(type(a) for a in args)
        for c in self._get_candidates(types):
            ret = c.func(*args)
            if ret is not NotImplemented:
                return ret
        return default

    EMPTY = object()

    def __call__(self, *args):
        ret = self.get(args, default=self.EMPTY)
        if ret is self.EMPTY:
            raise NotImplementedError('no valid candidates')
        return ret

    @property
    def op(self):
        def ret(*args):
            return self.get(args, default=NotImplemented)

        return ret

    def implementor(self, **kwargs) -> Union[Callable[[Callable], 'Implementor'], 'Implementor']:
        return Implementor(self).implementor(**kwargs)

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()
