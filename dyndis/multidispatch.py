from __future__ import annotations

from functools import partial, lru_cache
from itertools import chain
from numbers import Number
from typing import Dict, Tuple, List, Callable, Union, Iterable, TypeVar, Any, NamedTuple, Optional

from sortedcontainers import SortedDict, SortedList

from dyndis.candidate import Candidate
from dyndis.topological_ordering import TopologicalOrder
from dyndis.descriptors import MultiDispatchOp, MultiDispatchMethod, MultiDispatchStaticMethod
from dyndis.exceptions import NoCandidateError, AmbiguityError
from dyndis.implementor import Implementor
from dyndis.ranked_children import RankedChildrenTrie, RankedChildrenExhaustion
from dyndis.trie import Trie
from dyndis.type_keys.type_key import TypeVarKey, ClassKey, TypeKey, MatchException, MatchKind
from dyndis.util import RawReturnValue

CandTrie = Trie[TypeKey, Dict[Number, Candidate]]

RawNotImplemented = RawReturnValue(NotImplemented)


class AmbiguousBindingError(MatchException):
    """An error indicating that a type variable could not find a single type to bind to"""
    rank_offset = MatchKind.upcast

    def __init__(self, typevar, subclass, unrelated_classes):
        super().__init__(f'type variable {typevar} must up-cast type {subclass} to one of its constrained types,'
                         f' but it is a subclass of multiple non-related constraints: {unrelated_classes}'
                         f' (consider adding {subclass} as an explicit constraint in {typevar},'
                         f' or a specialized overload for {subclass})')


@lru_cache
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
            return ClassKey(minimal_candidates[0])
        elif scls.__bound__:
            return constrain_type(cls, scls.__bound__)
        return ClassKey(cls)
    return ClassKey(cls) if issubclass(cls, scls) else None


def process_new_layers(layers: Iterable[List[Candidate]]):
    """
    split universal minimal members into their own layers
    """
    ret = []
    for layer in layers:
        to = TopologicalOrder(layer)
        ret.extend(to.sorted_layers())
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


class QueuedVisit(NamedTuple):
    """
    A queued visitation of a trie for a search
    """
    rank: int
    depth: int
    trie: CandTrie
    var_dict: Dict[TypeVar, type]


class QueuedError(NamedTuple):
    """
    A queued error, signifying that an error occurred when searching a node of a certain rank
    """
    rank: int
    error: Optional[Exception]


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

        self.visitation_queue = SortedList(key=lambda x: -x.rank)
        self.visitation_queue.add(QueuedVisit(0, 0, owner.candidate_trie, {}))
        self.sorted = []

    def advance(self):
        """
        advance the search by 1 rank

        :return: only the members of the new rank, after adding them to the cache for future searches
        """
        ret = SortedDict()

        curr_rank = self.visitation_queue[-1].rank
        while self.visitation_queue:
            v_rank = self.visitation_queue[-1].rank
            if v_rank != curr_rank:
                break
            qv = self.visitation_queue[-1]
            if isinstance(qv, QueuedError):
                raise qv.error
            nexts = self.visit(qv, ret)
            # we only modify the queue after visit, because if an exception happened we want it to repeat
            self.visitation_queue.pop()
            self.visitation_queue.update(nexts)

        new_layers = process_new_layers(reversed(ret.values()))
        self.sorted.extend(new_layers)
        return new_layers

    def visit(self, qv: QueuedVisit, results: SortedDict[Any, List[Candidate]]):
        """
        evaluate a queued visit, adding all the candidates of the rank into results

        :param qv: the queued visit to evaluate
        :param results: the dict to add all valid candidates to
        :return: an iterator of all the future queued visits originating from this visit
        """
        if qv.depth == len(self.query):
            value = qv.trie.value(None)
            if value:
                for candidate in value.values():
                    add_priority(results, candidate)
            return
        curr_key = self.query[qv.depth]
        children: RankedChildrenExhaustion = qv.trie.children.exhaustion()
        child = children.exhaust(curr_key, None)
        if child:
            yield QueuedVisit(qv.rank, qv.depth + 1, child, qv.var_dict)

        # skip the fist element in mro, since it is an exact match
        mro = iter(curr_key.__mro__)
        next(mro)

        for child in children.exhaust_many(mro):
            yield QueuedVisit(qv.rank + 1, qv.depth + 1, child, qv.var_dict)

        for child_type, child in children.iter_unexhausted_special_items():
            next_var_dict = qv.var_dict
            if isinstance(child_type, TypeVarKey) and (child_type.inner not in next_var_dict):
                try:
                    constrained = constrain_type(curr_key, child_type.inner)
                except MatchException as e:
                    yield QueuedError(qv.rank + e.rank_offset, e)
                    continue
                if not constrained:
                    continue

                next_var_dict = dict(next_var_dict)
                next_var_dict[child_type.inner] = constrained

            match = child_type.match(curr_key, next_var_dict)
            if isinstance(match, MatchException):
                yield QueuedError(qv.rank + match.rank_offset, match)
            elif match is None:
                continue
            else:
                yield QueuedVisit(qv.rank + match, qv.depth + 1, child, next_var_dict)

    def __iter__(self):
        yield from self.sorted
        while self.visitation_queue:
            yield from self.advance()


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

        self.candidate_trie: CandTrie = RankedChildrenTrie()
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
        sd = self.candidate_trie.get(candidate.types)
        if sd is None:
            sd = self.candidate_trie[candidate.types] = SortedDict()
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
                raise AmbiguityError(layer, types)
            yield layer[0]

    def get(self, args, kwargs, default=None):
        """
        call the multidispatch with args as arguments, attempts all the appropriate candidate until one returns a
        non-NotImplemted value. If all the candidates are exhausted, returns default.

        :param args: the arguments for the multidispatch
        :param kwargs: keyword arguments forwarded directly to any attempted candidate
        :param default: the value to return if all candidates are exhausted
        """
        types = tuple(type(a) for a in args)
        for c in self._yield_candidates(types):
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

    def candidates(self):
        """
        get all the candidates defined in the multidispatch.
         Candidates are sorted by their priority, then topologically.
        """
        ret = SortedDict()
        for sd in self.candidate_trie.values():
            for k, v in sd.items():
                to = ret.get(k)
                if to is None:
                    to = ret[k] = TopologicalOrder()
                to.add(v)

        return chain.from_iterable(
            chain.from_iterable(to.sorted_layers()) for to in reversed(ret.values())
        )

    def __str__(self):
        if self.__name__:
            return f'<MultiDispatch {self.__name__}>'
        return super().__str__()
