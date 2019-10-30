from __future__ import annotations

from functools import partial
from itertools import chain
from numbers import Number
from typing import Dict, Tuple, List, Callable, Union, Optional, Iterable

from sortedcontainers import SortedDict

from dyndis.candidate import Candidate, get_least_key_index
from dyndis.implementor import Implementor
from dyndis.trie import Trie
from dyndis.util import RawReturnValue, AmbiguityError

CandTrie = Trie[type, Dict[Number, Candidate]]

RawNotImplemented = RawReturnValue(NotImplemented)


def process_new_layers(layers: List[List[Candidate]]):
    ret = []
    for layer in layers:
        while True:
            least_ind = get_least_key_index(layer)
            if least_ind == -1:
                break
            least = layer.pop(least_ind)
            ret.append((least,))
        ret.append(layer)
    return ret


def add_priority(seen_priorities: SortedDict[Number, List[Candidate]], candidate: Candidate):
    """
    Add a candidate to a temporary result dictionary
    :param seen_priorities: the sorted dict of existing candidates
    :param candidate: the candidate to add
    """
    eq_prio_list = seen_priorities.get(candidate.priority)
    if not eq_prio_list:
        eq_prio_list = seen_priorities[candidate.priority] = []
    eq_prio_list.append(candidate)


class CachedSearch:
    """
    A cached search for candidates of a specific type tuple
    """

    def __init__(self, owner: MultiDispatch, key: Tuple[type, ...]):
        """
        :param owner: the owning multidispatch
        :param key: the type tuple to use
        """
        ex = owner.candidates.get(key)
        if ex:
            lay_0 = [[v] for v in reversed(ex.values())]
        else:
            lay_0 = []

        self.sorted: List[List[Candidate]] = lay_0
        self.next_layer: List[Tuple[int, CandTrie]] = [(0, owner.candidates)]
        self.err: Optional[Exception] = None
        self.query = key

    def __iter__(self):
        yield from self.sorted
        while self.next_layer:
            yield from self.advance()

    def advance(self) -> Iterable[List[Candidate]]:
        """
        advance the search into the next layer, caching the result
        :return: the newly added candidates of this layer
        """
        ret = SortedDict()
        nexts: List[Tuple[int, CandTrie]] = []
        for (depth, n_trie) in self.next_layer:
            self.advance_search_inexact(n_trie, depth, ret, nexts)

        self.next_layer = nexts
        new_layers = process_new_layers(reversed(ret.values()))
        self.sorted.extend(new_layers)
        return new_layers

    def advance_search_inexact(self, current_trie: CandTrie, current_depth: int,
                               results: SortedDict[Number, List[Candidate]], nexts: List[Tuple[int, CandTrie]]):
        """
        advance the search by looking for candidates with at least one mismatch
        :param current_trie: the trie to conduct the search in
        :param current_depth: the current depth of the trie
        :param results: a list of candidates that match
        :param nexts: a list of tries to search in for the next layer
        """
        if current_depth == len(self.query):
            return
        curr_key = self.query[current_depth]
        for child_type, child in current_trie.children.items():
            if child_type is curr_key:
                self.advance_search_inexact(child, current_depth + 1, results, nexts)
            elif issubclass(curr_key, child_type):
                self.advance_search(child, current_depth + 1, results, nexts)

    def advance_search(self, current_trie: CandTrie, current_depth: int,
                       results: SortedDict[Number, List[Candidate]], nexts: List[Tuple[int, CandTrie]]):
        """
        advance the search by looking for candidates without any mismatches
        :param current_trie: the trie to conduct the search in
        :param current_depth: the current depth of the trie
        :param results: a list of candidates that match
        :param nexts: a list of tries to search in for the next layer
        """
        if current_depth == len(self.query):
            curr_value = current_trie.value(None)
            if curr_value:
                for candidate in curr_value.values():
                    add_priority(results, candidate)
            return
        curr_key = self.query[current_depth]
        next_exact = current_trie.children.get(curr_key)
        if next_exact:
            self.advance_search(next_exact, current_depth + 1, results, nexts)
        nexts.append((current_depth, current_trie))


EMPTY = object()


class MultiDispatch:
    """
    The central class, a callable that can delegate to multiple candidates depending on the types of parameters
    """

    def __init__(self, name: str = None, doc: str = None):
        """
        :param name: an optional name for the callable
        :param doc: an optional doc for the callable
        """
        self.__name__ = name
        self.__doc__ = doc

        self.candidates: CandTrie = Trie()
        self.cache: Dict[int, Dict[Tuple[type, ...], CachedSearch]] = {}

    def _clean_cache(self, sizes: Iterable[int]):
        """
        clear the candidate cache for all type tuples of the sizes specified
        :param sizes: the sizes for which to clear to cache
        """
        for size in sizes:
            self.cache.pop(size, None)

    def _add_candidate(self, candidate: Candidate, clean_cache=True):
        """
        Add a single candidate to the multidispatch. If the multidispatch has no set name or doc,
         the name or doc of the candidate will be used (if available)
        :param candidate: the candidate to add
        :param clean_cache: whether to clean the relevant cache
        """
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
        if clean_cache:
            self._clean_cache((len(candidate.types),))

    def add_candidates(self, candidates: Iterable[Candidate]):
        """
        Add a collection of candiates to the multidispatch. If the multidispatch has no set name or doc,
         the name or doc of the first candidate with the relevant attributes will be used.
        :param candidates: an iterable of candidates to be added.
        """
        clean_sizes = set()
        for cand in candidates:
            self._add_candidate(cand, clean_cache=False)
            clean_sizes.add(len(cand.types))
        self._clean_cache(clean_sizes)
        return self

    def add_func(self, priority=0, symmetric=False, func=None):
        """
        Adds candidates to a multidispatch generated from a function, usable as a
        :param priority: the priority of the candidates.
        :param symmetric: if set to true, the permutations of all the candidates are added as well
        :param func: the function to used
        """
        if not func:
            return partial(self.add_func, priority, symmetric)
        cands = Candidate.from_func(priority, func)
        if symmetric:
            cands = chain.from_iterable(c.permutations() for c in cands)
        self.add_candidates(cands)
        return self

    def _yield_candidates(self, types):
        """
        yield all the relevant candidates for a type tuple, sorted first by number of upcasts required (ascending),
         and second by priority (descending)
        :param types: the type tuple to get candidates for
        """
        sub_cache = self.cache.get(len(types))
        if not sub_cache:
            sub_cache = self.cache[len(types)] = {}
            cache = sub_cache[types] = CachedSearch(self, types)
        else:
            cache = sub_cache.get(types)
            if not cache:
                cache = sub_cache[types] = CachedSearch(self, types)

        for layer in cache:
            if len(layer) != 1:
                raise AmbiguityError(f'multiple candidates of equal rank and priority: {layer} for key <'
                                     + ", ".join(t.__name__ for t in types) + ">")
            yield layer[0]

    # todo allow kwargs (don't type check, just inject)
    def get(self, args, default=None):
        """
        call the multidispatch with args as arguments, attempts all the appropriate candidate until
         one returns a non-NotImplemted value. If all the candidates are exhausted, returns default.
        :param args: the arguments for the multidispatch
        :param default: the value to return if all candidates are exhausted
        """
        types = tuple(type(a) for a in args)
        for c in self._yield_candidates(types):
            ret = c.func(*args)
            if ret is not NotImplemented:
                return RawReturnValue.unwrap(ret)
        return default

    def __call__(self, *args):
        """
        call the multidispatch and raise an error if no candidates are found
        """
        ret = self.get(args, default=EMPTY)
        if ret is EMPTY:
            raise NotImplementedError(
                'no valid candidates for argument types <' + ", ".join(type(a).__name__ for a in args) + '>'
            )
        return ret

    @property
    def op(self):
        """
        :return: an adapter for the multidispatch to be used as an adapter, returning NotImplemented if no candidates match,
         and setting the multidispatch's name if necessary
        """
        return MultiDispatchOp(self)

    def implementor(self, *args, **kwargs) -> Union[Callable[[Callable], 'Implementor'], 'Implementor']:
        """
        create an Implementor for the multidispatch and call its implementor method with the arguments
        """
        return Implementor(self).implementor(*args, **kwargs)

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()


class MultiDispatchOp:
    """
    An operator adapter for a multidispatch
    """

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
