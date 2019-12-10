from __future__ import annotations

from functools import partial
from itertools import chain, combinations, product
from typing import Dict, Tuple, List, Callable, Union, Iterable, Optional, Iterator

from sortedcontainers import SortedSet

from dyndis.ambiguity_set import PotentialConflictSet
from dyndis.candidate import Candidate
from dyndis.descriptors import MultiDispatchOp, MultiDispatchMethod, MultiDispatchStaticMethod, MultiDispatchClassMethod
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.implementor import Implementor
from dyndis.topological_set import TopologicalSet
from dyndis.type_keys.type_key import MatchException, TypeVarKey, class_type_key, all_subclasses
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

        self.layer_iter = owner.candidate_topsets[len(key)].layers()

        self.sorted = []

    def advance(self):
        layer: Optional[List[Candidate]] = next(self.layer_iter, None)
        if layer is None:
            self.layer_iter = None
            return None
        ret = []
        for cand in layer:
            v = cand.match(self.query)
            if isinstance(v, MatchException):
                # ensure the error will be raised again if called
                self.layer_iter = chain([layer], self.layer_iter)
                raise v
            if v:
                if not ret or ret[-1][0].priority != cand.priority:
                    ret.append([cand])
                else:
                    ret[-1].append(cand)

        self.sorted.extend(reversed(ret))
        yield from reversed(ret)

    def __iter__(self):
        yield from self.sorted
        while self.layer_iter:
            yield from self.advance()


EMPTY = object()


class MultiDispatch:
    """
    The central class, a callable that can delegate to multiple candidates depending on the types of parameters
    """

    class TieredTopologicalSet(TopologicalSet):
        @staticmethod
        def gt_factory():
            return SortedSet(key=lambda x: x.inner.priority)

    def __init__(self, name: str = None, doc: str = None):
        """
        :param name: an optional name for the callable
        :param doc: an optional doc for the callable
        """
        self.__name__ = name
        self.__doc__ = doc

        # self.candidate_trie: CandTrie = RankedChildrenTrie()
        self.candidate_topsets: Dict[int, TopologicalSet[Candidate]] = {}
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
        sc = self.candidate_topsets.get(len(candidate.types))
        if sc is None:
            sc = self.candidate_topsets[len(candidate.types)] = self.TieredTopologicalSet()
        if not sc.add(candidate):
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
        Add a collection of candiates to the multidispatch. If the multidispatch has no set name or doc, the name or doc of the first candidate with the relevant attributes will be used.

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
        :param func: the function to used
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
        :return: an adapter for the multidispatch to be used as an adapter, returning NotImplemented if no candidates match,
         and setting the multidispatch's name if necessary
        """
        return MultiDispatchOp(self)

    def method(self):
        """
        :return: an adapter for the multidispatch to be used as a method, raising error if no candidates match,
         and setting the multidispatch's name if necessary
        """
        return MultiDispatchMethod(self)

    def classmethod(self):
        """
        :return: an adapter for the multidispatch to be used as a class method, raising error if no candidates match,
         and setting the multidispatch's name if necessary
        """
        return MultiDispatchClassMethod(self)

    def staticmethod(self):
        """
        :return: an adapter for the multidispatch to be used as a static method, raising error if no candidates match,
         and setting the multidispatch's name if necessary
        """
        return MultiDispatchStaticMethod(self)

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
        return chain.from_iterable(self.candidate_topsets.values())

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()

    def potential_conflicts(self, clear_subclass_cache = True) -> PotentialConflictSet:
        def sub_layers(layer: Iterable[Candidate]):
            s_layer = []
            for i in layer:
                if s_layer and i.priority != s_layer[-1].priority:
                    yield s_layer
                    s_layer = [i]
                else:
                    s_layer.append(i)
            if s_layer:
                yield s_layer

        def conf_layer(layer: Iterable[Candidate], ret: PotentialConflictSet):
            def get_ambiguities(types0, types1, dict0, dict1):
                if not types0:
                    assert not types1
                    return [[]]

                t0, *r0 = types0
                t1, *r1 = types1
                m0 = t0.match_types(dict0)
                m1 = t1.match_types(dict1)
                amb_set = m0 & m1
                if not amb_set:
                    return None
                t0_undefined = isinstance(t0, TypeVarKey) and t0.inner not in dict0
                t1_undefined = isinstance(t1, TypeVarKey) and t1.inner not in dict1
                if not (t0_undefined or t1_undefined):
                    sa = get_ambiguities(r0, r1, dict0, dict1)
                    if sa is None:
                        return None
                    ret = [[amb_set, *s] for s in sa]
                else:
                    ret = []
                    for a, b in product(m0, m1):
                        if t0_undefined:
                            dict0[t0.inner] = class_type_key(a)
                        if t1_undefined:
                            dict1[t1.inner] = class_type_key(b)
                        sa = get_ambiguities(r0, r1, dict0, dict1)
                        if sa is None:
                            continue
                        ret.extend([{a}, *s] for s in sa)
                    if t0_undefined:
                        del dict0[t0.inner]
                    if t1_undefined:
                        del dict1[t1.inner]
                return ret

            def get_errors(types, dict_, i=0):
                if not types:
                    return
                t, *r = types
                err_types = t.error_types(dict_)
                if err_types:
                    yield i, err_types, dict(dict_)
                    return

                t_undefined = isinstance(t, TypeVarKey) and t.inner not in dict_
                if t_undefined:
                    matches = t.match_types(dict_)
                    for m in matches:
                        dict_[t.inner] = class_type_key(m)
                        yield from get_errors(r, dict_, i+1)
                    del dict_[t.inner]
                else:
                    yield from get_errors(r, dict_, i+1)

            def process_err_cand(cand):
                errs = list(get_errors(cand.types, {}, 0))
                for i, et, dvr in errs:
                    for t, ex_t in et:
                        ret.add_error(i, t, ex_t, dvr, c0)

            for s_layer in sub_layers(layer):
                for c0, c1 in combinations(s_layer, 2):
                    process_err_cand(c0)
                    for amb in get_ambiguities(c0.types, c1.types, {}, {}) or ():
                        ret.add_ambiguities(tuple(amb), {c0, c1})
                process_err_cand(s_layer[-1])

        ret = PotentialConflictSet(self)

        for ts in self.candidate_topsets.values():
            for layer in ts.layers():
                conf_layer(layer, ret)

        if clear_subclass_cache:
            all_subclasses.cache_clear()

        return ret
