from __future__ import annotations

from itertools import chain
from typing import TypeVar, Set, Union, MutableSet, Any, MutableMapping, List, Iterator, Sequence

from sortedcontainers import SortedDict

from dyndis.candidate import Candidate
from dyndis.trie import Trie, TrieNode
from dyndis.type_keys.type_key import TypeKey, MatchException, TypeVarKey

T = TypeVar('T')


class TopologicalNode:
    """
    A node of an element in a topological set
    """
    __slots__ = 'inner', 'gt', 'lt', '_layer'

    def __init__(self, inner: Candidate):
        self.inner = inner
        # rule: if root is in lt, then len(gt) == 1
        self.lt: Set[Union[TopologicalNode, TopologicalRootNode]] = set()
        self.gt: Set[TopologicalNode] = set()

        self._layer = None

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.inner < other.inner

    def layer(self):
        if self._layer is None:
            self._layer = max(l.layer() for l in self.lt) + 1
        return self._layer

    def invalidate_layer(self):
        self._layer = None


class TopologicalRootNode:
    """
    The virtual root node of a topological set. This is a handy wrapper for a set's first layer, allowing it to be used
     as a node
    """

    def __init__(self, owner: TopologicalSet):
        self.owner = owner

    @property
    def gt(self):
        if not self.owner.layers:
            return frozenset()
        return self.owner.layers[0]

    def __lt__(self, other):
        return True

    def layer(self):
        return -1


class CandidateSet(MutableSet[TopologicalNode]):
    """
    A set that stores candidates of equal rank in easy-to-query tries
    """

    def __init__(self):
        self.tries: MutableMapping[Any, Trie[TypeKey, TopologicalNode]] = SortedDict()

    def add(self, cand: TopologicalNode):
        trie = self.tries.get(cand.inner.priority)
        if trie is None:
            trie = self.tries[cand.inner.priority] = Trie()
        trie[cand.inner.types] = cand

    def remove(self, cand: TopologicalNode):
        trie = self.tries.get(cand.inner.priority)
        if trie is None:
            raise KeyError(cand)
        del trie[cand.inner.types]
        if not trie:
            del self.tries[cand.inner.priority]

    def discard(self, x) -> None:
        try:
            self.remove(x)
        except KeyError:
            pass

    def __len__(self):
        return sum(len(t) for t in self.tries.values())

    def __iter__(self):
        for trie in reversed(self.tries.values()):
            yield from trie.values()

    def clear(self) -> None:
        self.tries.clear()

    def __contains__(self, cand):
        trie = self.tries.get(cand.inner.priority)
        if trie is None:
            return False
        return cand.inner.types in trie

    def by_sublayer(self, query: Sequence[type]):
        """
        :return: for each priority in self (in decreasing order), yields all the candidates of that priority that match
         the query
        """

        def _matches(node: TrieNode[TypeKey, TopologicalNode], ind, defined_type_vars):
            if ind == len(query):
                if node.has_value:
                    yield node.value()
                return
            q = query[ind]
            for k, child in node.children.items():
                new_dtv = defined_type_vars
                if isinstance(k, TypeVarKey) and k.inner not in new_dtv:
                    constrained = k.constrain_type(q, k.inner)
                    if not constrained:
                        continue
                    new_dtv = dict(new_dtv)
                    new_dtv[k.inner] = constrained
                    match = True
                else:
                    match = k.match(q, new_dtv)
                    if isinstance(match, MatchException):
                        raise match

                if match:
                    yield from _matches(child, ind + 1, new_dtv)

        for t in reversed(self.tries.values()):
            yield _matches(t.root, 0, {})


class TopologicalSet(MutableSet[Candidate]):
    """
    A set that allows for quick topological sorting of its elements, supporting weakly ordered elements
    """

    def __init__(self, arg=()):
        self.root = TopologicalRootNode(self)
        self.layers: List[CandidateSet] = []
        self._len = 0
        for a in arg:
            self.add(a)

    def add(self, x) -> bool:
        """
        :return: True if all went well, False if an equivalent element was found in the set
        """
        node = TopologicalNode(x)

        potential_parents: Set = {self.root}
        direct_parents = []
        direct_children = []
        while potential_parents:
            pp = potential_parents.pop()
            any_subchildren = False
            for k in pp.gt:
                if k < node:
                    potential_parents.add(k)
                    any_subchildren = True
                elif node < k:
                    direct_children.append(k)
                elif node.inner <= k.inner and k.inner >= node.inner:
                    return False
            if not any_subchildren:
                direct_parents.append(pp)

        for dp in direct_parents:
            node.lt.add(dp)
            if dp is not self.root:
                dp.gt.add(node)

        for dc in direct_children:
            supplanted = dc.lt & node.lt
            for s in supplanted:
                if s is not self.root:
                    s.gt.remove(dc)
            dc.lt.difference_update(supplanted)
            dc.lt.add(node)
            node.gt.add(dc)
            self._rebase(dc)

        layer = node.layer()
        if len(self.layers) == layer:
            self.layers.append(CandidateSet())
        self.layers[layer].add(node)

        return True

    def _rebase(self, candidate: TopologicalNode):
        """
        remove a node from its current layer, and place it in its appropriate layer, and similarly rebase all its
         children
        """
        prev_layer = candidate.layer()
        candidate.invalidate_layer()
        new_layer = candidate.layer()
        if new_layer == prev_layer:
            return
        self.layers[prev_layer].remove(candidate)
        if len(self.layers) <= new_layer:
            self.layers.append(CandidateSet())
        self.layers[new_layer].add(candidate)
        for child in candidate.gt:
            self._rebase(child)

    def __contains__(self, item):
        raise NotImplementedError

    def remove(self, x) -> None:
        raise NotImplementedError

    def discard(self, x) -> None:
        try:
            self.remove(x)
        except KeyError:
            pass

    def __iter__(self):
        return chain.from_iterable(self.layers)

    def __len__(self):
        return self._len

    def clear(self) -> None:
        self._len = 0
        self.root.gt.clear()
        self.layers.clear()
