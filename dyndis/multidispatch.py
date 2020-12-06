from __future__ import annotations

from functools import partial
from itertools import chain
from typing import Dict, Tuple, List, Callable, Union, Iterable, Optional, Iterator

from dyndis.candidate import Candidate
from dyndis.descriptors import MultiDispatchOp
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.implementor import Implementor
from dyndis.topological_set import TopologicalSet, CandidateSet
from dyndis.type_keys.type_key import MatchException
from dyndis.util import RawReturnValue

RawNotImplemented = RawReturnValue(NotImplemented)


class CachedSearch:
    """
    A cached search for candidates of a specific type tuple
    """

    def __init__(self, owner: MultiDispatch, key: Tuple[type, ...]):
        """
        :param owner: the owning multidispatch
        :param key: the type tuple to use
        """
        self.query = key

        self.layer_iter = iter(owner.candidate_set.layers)

        self.sorted = []

    def advance(self):
        """
        advance the search by one layer, and cache the results
        :return: the new candidates added to the sorted list
        """
        layer: Optional[CandidateSet] = next(self.layer_iter, None)
        if layer is None:
            self.layer_iter = None
            return None

        try:
            sub_layers = layer.by_sublayer(self.query)
        except MatchException:
            # ensure the error will be raised again if called
            self.layer_iter = chain([layer], self.layer_iter)
            raise

        sl = [[c.inner for c in s] for s in sub_layers]
        self.sorted.extend(sl)
        return sl

    def __iter__(self):
        yield from self.sorted
        while self.layer_iter:
            next_layers = self.advance()
            if next_layers is not None:
                yield from next_layers


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

        # self.candidate_trie: CandTrie = RankedChildrenTrie()
        self.candidate_set: TopologicalSet[Candidate] = TopologicalSet()
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
        Add a single candidate to the multidispatch. If the multidispatch has no set name or doc, the name or doc of
        the candidate will be used (if available)

        :param candidate: the candidate to add
        :param clean_cache: whether to clean the relevant cache
        """
        if not self.candidate_set.add(candidate):
            raise ValueError(f'A candidate of equal types ({candidate.types})'
                             f' and priority ({candidate.priority}) exists')

        if not self.__name__:
            self.__name__ = candidate.__name__
        if not self.__doc__:
            self.__doc__ = candidate.__doc__
        if clean_cache:
            self._clean_cache((len(candidate.types),))

    def add_candidates(self, candidates: Iterable[Candidate]):
        """
        Add a collection of candiates to the multidispatch. If the multidispatch has no set name or doc, the name or doc
         of the first candidate with the relevant attributes will be used.

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
        Adds candidates to a multidispatch generated from a function, usable as a decorator

        :param priority: the priority of the candidates.
        :param symmetric: if set to true, the permutations of all the candidates are added as well
        :param func: the function to register
        """
        if not func:
            if callable(priority):
                func = priority
                priority = 0
            else:
                return partial(self.add_func, priority, symmetric)
        cands = Candidate.from_func(priority, func)
        if symmetric:
            cands = chain.from_iterable(c.permutations() for c in cands)
        self.add_candidates(cands)
        return self

    def _yield_layers(self, types):
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

        return cache

    def get(self, args, kwargs, default=None):
        """
        call the multidispatch with args as arguments, attempts all the appropriate candidate until one returns a
        non-NotImplemted value. If all the candidates are exhausted, returns default.

        :param args: the arguments for the multidispatch
        :param kwargs: keyword arguments forwarded directly to any attempted candidate
        :param default: the value to return if all candidates are exhausted
        """
        types = tuple(type(a) for a in args)
        for layer in self.candidates_for_types(*types):
            if len(layer) == 0:
                continue
            if len(layer) != 1:
                raise AmbiguityError(layer, types)
            c = layer[0]
            ret = c.func(*args, **kwargs)
            if ret is not NotImplemented:
                return RawReturnValue.unwrap(ret)
        return default

    def __call__(self, *args, **kwargs):
        """
        call the multidispatch and raise an error if no candidates are found
        """
        ret = self.get(args, kwargs, default=EMPTY)
        if ret is EMPTY:
            raise NoCandidateError(args)
        return ret

    def op(self):
        """
        :return: an adapter for the multidispatch to be used as an adapter, returning NotImplemented if no candidates
         match, and setting the multidispatch's name if necessary
        """
        return MultiDispatchOp(self)

    def implementor(self, *args, **kwargs) -> Union[Callable[[Callable], 'Implementor'], 'Implementor']:
        """
        create an Implementor for the MultiDispatch and call its implementor method with the arguments
        """
        return Implementor(self).implementor(*args, **kwargs)

    def candidates_for_types(self, *arg_types) -> Iterator[List[Candidate]]:
        """
        get candidate layers as they are attempted for a set of argument types
        """
        return iter(self._yield_layers(arg_types))

    def candidates(self) -> Iterator[Candidate]:
        """
        get all the candidates defined in the multidispatch.
         Candidates are sorted by their priority, then topologically.
        """
        return map(lambda x: x.inner, self.candidate_set)

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()

    def __get__(self, instance, owner):
        if instance:
            return partial(self, instance)
        return self
