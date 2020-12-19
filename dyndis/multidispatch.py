from __future__ import annotations

from abc import get_cache_token
from collections import defaultdict, ChainMap
from functools import partial
from inspect import signature, Parameter
from typing import Callable, TypeVar, Generic, Dict, Set, List, Mapping, get_type_hints, Union, Tuple, Optional, \
    MutableMapping
from weakref import WeakValueDictionary, proxy


from dyndis.annotation_filter import AnnotationFilter, annotation_filter
from dyndis.exceptions import AmbiguityError
from dyndis.implementor import Implementor
from dyndis.topological_sort import topological_sort
from dyndis.weaktupledict import WeakTupleDict

T = TypeVar('T')


class Candidate(Generic[T]):
    def __init__(self, callback: Callable[..., T], filters: Tuple[AnnotationFilter], owner: MultiDispatch, *,
                 initial_definitions: Optional[Dict[TypeVar, AnnotationFilter]] = None):
        self.callback = callback
        self.filters = filters
        self.owner = proxy(owner)
        self.initial_definitions = initial_definitions or {}

    def __str__(self):
        return self.owner.__name__ + "<" + ", ".join(str(f) for f in self.filters) + ">"

    def envelops(self, other: Candidate):
        partial = False
        for a, b in zip(self.filters, other.filters):
            if a.envelops(b):
                if b.envelops(a):
                    # a and b are equivalent
                    continue
                partial = True
            else:
                return False
        return partial

    def match(self, args):
        defined = dict(self.initial_definitions)
        for a, f in zip(args, self.filters):
            r = f.match(a, defined)
            if not r:
                return False
            if isinstance(r, Mapping):
                defined.update(r)
        return True


LookupLayer = Union[Exception, Candidate]


class MultiDispatch(Generic[T], Callable[..., T]):
    _Implementors: MutableMapping[str, Implementor] = WeakValueDictionary()

    def __init__(self, default_callback: Callable[..., T]):
        self.default_callback = default_callback
        self.__name__ = default_callback.__name__
        self.candidate_sets: Dict[int, Set[Candidate]] = defaultdict(set)

        self._cache_token = get_cache_token()
        self._layers_cache: Dict[int, List[Set[Candidate]]] = {}
        self._lookup_cache: Dict[int, WeakTupleDict[List[LookupLayer]]] = defaultdict(WeakTupleDict)

    def _add_candidate(self, func, filters, **kwargs):
        cand = Candidate(func, filters, self, **kwargs)
        self.candidate_sets[len(filters)].add(cand)

        self.clear_cache(len(filters))

    def clear_cache(self, arg_len=None):
        if arg_len is None:
            self._layers_cache.clear()
            self._lookup_cache.clear()
        else:
            self._layers_cache.pop(arg_len, None)
            self._lookup_cache.pop(arg_len, None)

    def _topological_candidates(self, func_len) -> List[Set[Candidate]]:
        if func_len in self._layers_cache:
            return self._layers_cache[func_len]
        ret = self._layers_cache[func_len] = list(topological_sort(self.candidate_sets[func_len]))
        return ret

    def _get_lookup_layers(self, t_args: Tuple[type, ...]) -> List[LookupLayer]:
        cached_lookup = self._lookup_cache[len(t_args)].get(t_args)
        if cached_lookup is not None:
            return cached_lookup
        ret = []
        tc = self._topological_candidates(len(t_args))
        for layer in tc:
            try:
                valid_cands = [c for c in layer if c.match(t_args)]
            except TypeError as e:
                ret.append(e)
                break
            if len(valid_cands) == 1:
                ret.append(valid_cands[0])
            elif valid_cands:
                ret.append(AmbiguityError(f'ambiguous call between {", ".join(str(v) for v in valid_cands)}'))
                break
        self._lookup_cache[len(t_args)][t_args] = ret
        return ret

    def __call__(self, *args, **kwargs):
        new_cache_token = get_cache_token()
        if new_cache_token != self._cache_token:
            # our cache is out of date and must be rebuilt
            self.clear_cache()
            self._cache_token = new_cache_token

        t_args = tuple(type(a) for a in args)
        ll = self._get_lookup_layers(t_args)
        for layer in ll:
            if isinstance(layer, Exception):
                raise layer
            ret = layer.callback(*args, **kwargs)
            if ret is not NotImplemented:
                return ret
        return self.default_callback(*args, **kwargs)

    def register(self, func=None, extra_namespace=None, default_annotations=None, **kwargs):
        if not func:
            return partial(self.register, **kwargs)

        sign = signature(func)
        type_hints = get_type_hints(func, localns=extra_namespace)
        if default_annotations:
            type_hints = ChainMap(default_annotations, type_hints)
        filters = []
        for p in sign.parameters.values():
            if p.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD, Parameter.POSITIONAL_ONLY):
                break
            if p.name not in type_hints:
                raise TypeError(f'parameter {p.name} is not annotated')
            filter_ = annotation_filter(type_hints[p.name])
            filters.append(filter_)
        self._add_candidate(func, tuple(filters), **kwargs)
        return func

    def implement(self, key, **kwargs):
        implementor = self._Implementors.get(key)
        if not implementor:
            implementor = self._Implementors[key] = Implementor()
        return partial(implementor, self, kwargs)

    def __get__(self, instance, owner):
        if instance:
            return partial(self, instance)
        return self
