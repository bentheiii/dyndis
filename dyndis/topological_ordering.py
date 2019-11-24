from typing import Dict, MutableSet, NamedTuple

from dyndis.candidate import Candidate, cmp_key


class _TopologicalOrdering(NamedTuple):
    previous: MutableSet[Candidate]
    after: MutableSet[Candidate]


class TopologicalOrder(Dict[Candidate, _TopologicalOrdering]):
    def __init__(self, cands=()):
        super().__init__()
        for c in cands:
            self.add(c)

    def add(self, new_cand: Candidate):
        to = _TopologicalOrdering(set(), set())
        for existing_cand, eto in self.items():
            cmp = cmp_key(new_cand.types, existing_cand.types)
            if cmp == 1:
                eto.after.add(new_cand)
                to.previous.add(existing_cand)
            elif cmp == -1:
                eto.previous.add(new_cand)
                to.after.add(existing_cand)
        self[new_cand] = to

    def sorted(self):
        waiting: Dict[Candidate, _TopologicalOrdering] = {}
        no_prev: Dict[Candidate, _TopologicalOrdering] = {}
        for k, v in self.items():
            if v.previous:
                waiting[k] = _TopologicalOrdering(set(v.previous), v.after)
            else:
                no_prev[k] = v

        while no_prev:
            ret = []
            new_no_prev = {}
            for k, v in no_prev.items():
                ret.append(k)
                for after in v.after:
                    p = waiting[after].previous
                    p.remove(k)
                    if not p:
                        new_no_prev[after] = waiting.pop(after)
            yield ret
            no_prev = new_no_prev

        assert not waiting
