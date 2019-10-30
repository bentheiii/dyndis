from __future__ import annotations

from functools import partial
from numbers import Number
from typing import Dict, Tuple, List, Callable, Union, Optional, Iterable

from sortedcontainers import SortedDict

from dyndis.candidate import Candidate
from dyndis.implementor import Implementor
from dyndis.trie import Trie

CandTrie = Trie[type, Dict[Number, Candidate]]


# todo tertiary candidates with conditions
class CachedSearch:
    def __init__(self, owner: MultiDispatch, key: Tuple[type, ...]):
        ex = owner.candidates.get(key)
        if ex:
            lay_0 = list(ex.values())
        else:
            lay_0 = []

        self.sorted: List[Candidate] = lay_0
        self.next_layer: List[Tuple[int, CandTrie]] = [(0, owner.candidates)]
        self.err: Optional[Exception] = None
        self.query = key

    def ensure(self):
        if self.err:
            raise self.err

    def advance(self) -> Iterable[Candidate]:
        self.ensure()
        ret = SortedDict()
        nexts: List[Tuple[int, CandTrie]] = []
        for (depth, n_trie) in self.next_layer:
            self.advance_search_inexact(n_trie, depth, ret, nexts)

        self.next_layer = nexts
        self.sorted.extend(ret.values())
        return ret.values()

    def raise_(self, error: Exception):
        self.err = error
        raise error

    def add_priority(self, seen_priorities: SortedDict[Number, Candidate], candidate: Candidate):
        extant = seen_priorities.setdefault(candidate.priority, candidate)
        if extant is not candidate:
            self.raise_(Exception(
                f'multiple candidates of equal priority for arguements of types <{", ".join(t.__name__ for t in self.query)}>: {candidate} and {extant} (maybe more)'
            ))

    def advance_search_inexact(self, current_trie: CandTrie, current_depth: int,
                               results: SortedDict[Number, Candidate], nexts: List[Tuple[int, CandTrie]]):
        if current_depth == len(self.query):
            return
        curr_key = self.query[current_depth]
        for child_type, child in current_trie.children.items():
            if child_type is curr_key:
                self.advance_search_inexact(child, current_depth + 1, results, nexts)
            elif issubclass(curr_key, child_type):
                self.advance_search(child, current_depth + 1, results, nexts)

    def advance_search(self, current_trie: CandTrie, current_depth: int,
                       results: SortedDict[Number, Candidate], nexts: List[Tuple[int, CandTrie]]):
        if current_depth == len(self.query):
            curr_value = current_trie.value(None)
            if curr_value:
                for candidate in curr_value.values():
                    self.add_priority(results, candidate)
            return
        curr_key = self.query[current_depth]
        next_exact = current_trie.children.get(curr_key)
        if next_exact:
            self.advance_search(next_exact, current_depth + 1, results, nexts)
        nexts.append((current_depth, current_trie))


class MultiDispatch:
    def __init__(self, name: str = None, doc: str = None):
        self.__name__ = name
        self.__doc__ = doc

        self.candidates: CandTrie = Trie()
        self.cache: Dict[int, Dict[Tuple[type, ...], CachedSearch]] = {}

    def _clean_secondary_cache(self, size):
        self.cache.pop(size, None)

    def _add_candidate(self, candidate: Candidate, clean_secondary_cache=True):
        sd = self.candidates.get(candidate.types)
        if sd is None:
            sd = self.candidates[candidate.types] = SortedDict()
        if candidate.priority in sd:
            raise ValueError(f'cannot insert candidate, a candidate of equal types ({candidate.types})'
                             f' and priority ({candidate.priority}) exists ')
        sd[candidate.priority] = candidate

        if not self.__name__:
            self.__name__ = candidate.__name__
        if not self.__doc__:
            self.__doc__ = candidate.__doc__
        if clean_secondary_cache:
            self._clean_secondary_cache(len(candidate.types))

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

    def _yield_candidates(self, types):
        sub_cache = self.cache.get(len(types))
        if not sub_cache:
            sub_cache = self.cache[len(types)] = {}
            cache = sub_cache[types] = CachedSearch(self, types)
        else:
            cache = sub_cache.get(types)
            if not cache:
                cache = sub_cache[types] = CachedSearch(self, types)

        if cache.sorted:
            yield from cache.sorted

        while cache.next_layer:
            next_layer = cache.advance()
            yield from next_layer

    def get(self, args, default=None):
        types = tuple(type(a) for a in args)
        for c in self._yield_candidates(types):
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
        return MultiDispatchOp(self)

    def implementor(self, **kwargs) -> Union[Callable[[Callable], 'Implementor'], 'Implementor']:
        return Implementor(self).implementor(**kwargs)

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()


class MultiDispatchOp:
    def __init__(self, md: MultiDispatch):
        self.md = md

    def __set_name__(self, owner, name):
        if not self.md.__name__:
            self.md.__name__ = name

    def __get__(self, instance, owner):
        if instance:
            return partial(self.__call__, instance)
        return self

    def __call__(self, *args):
        return self.md.get(args, default=NotImplemented)
