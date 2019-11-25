from itertools import chain
from typing import Dict, MutableSet, NamedTuple, AbstractSet, Container, Tuple

from dyndis.candidate import Candidate
from dyndis.type_keys.type_key import TypeKey


class TopologicalRanking(NamedTuple):
    """
    A ranking of a candidate in a topological sorting
    """
    previous: MutableSet[Candidate]  # all the candidates that come before this one
    after: MutableSet[Candidate]  # all the candidates that come after this one


def cmp_typeset(lhs: Tuple[TypeKey, ...], rhs: Tuple[TypeKey, ...]):
    """
    compares two typekey tuples, checking whether one is a strict sub-key of the other
    * -1: lhs[i] <= rhs[i] for all i
    * 1:  lhs[i] >= rhs[i] for all i
    * 0: neither are a sub-key of the other
    It is an error to send equal tuples, or tuples of different lengths
    """
    ret = 0
    for left, right in zip(lhs, rhs):
        if ret < 0:
            try:
                cmp = left <= right
            except TypeError:
                return 0
            if not cmp:
                return 0
        elif ret > 0:
            try:
                cmp = right <= left
            except TypeError:
                return 0
            if not cmp:
                return 0
        else:
            try:
                if left < right:
                    ret = -1
                elif right < left:
                    ret = 1
            except TypeError:
                return 0
    return ret


class TopologicalOrder(AbstractSet[Container]):
    """
    A data structure that orders candidates such that a candidate will appear after all
     other candidates whose key is a sub-key to theirs
    """

    def __init__(self, cands=()):
        """
        :param cands: the candidates to add to the order
        """
        self.inner: Dict[Candidate, TopologicalRanking] = {}
        for c in cands:
            self.add(c)

    def add(self, new_cand: Candidate):
        """
        add a candidate to the order
        :param new_cand: the candidate to add
        """
        to = TopologicalRanking(set(), set())
        for existing_cand, eto in self.inner.items():
            cmp = cmp_typeset(new_cand.types, existing_cand.types)
            if cmp == 1:
                eto.after.add(new_cand)
                to.previous.add(existing_cand)
            elif cmp == -1:
                eto.previous.add(new_cand)
                to.after.add(existing_cand)
        self.inner[new_cand] = to

    def sorted_layers(self):
        """
        :return: all the elements in self, such as each layer is maximal and precedes the ones after it
        """
        waiting: Dict[Candidate, TopologicalRanking] = {}
        no_prev: Dict[Candidate, TopologicalRanking] = {}
        for k, v in self.inner.items():
            if v.previous:
                waiting[k] = TopologicalRanking(set(v.previous), v.after)
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

    def __contains__(self, item):
        return item in self.inner

    def __iter__(self):
        yield from chain.from_iterable(self.sorted_layers())

    def __len__(self):
        return len(self.inner)
