from __future__ import annotations

from itertools import chain
from types import new_class
from typing import Callable, Generic, TypeVar, Set, Union, Dict, Iterable, MutableSet

T = TypeVar('T')


class NodeSuper:
    lt_factory = set
    gt_factory = set


class TopologicalNode(Generic[T], NodeSuper):
    def __init__(self, inner: T):
        self.inner = inner
        # rule: if root is in lt, then len(gt) == 1
        self.lt: Set[Union[TopologicalNode[T], TopologicalRootNode[T]]] = self.lt_factory()
        self.gt: Set[TopologicalNode[T]] = self.gt_factory()

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.inner < other.inner


class TopologicalRootNode(Generic[T], NodeSuper):
    def __init__(self):
        self.gt: Set[TopologicalNode[T]] = self.gt_factory()

    def __lt__(self, other):
        return True


class TopologicalSet(MutableSet[T], Generic[T]):
    node_factory: Callable[[], TopologicalNode] = TopologicalNode
    root_factory = TopologicalRootNode

    def __init__(self, arg=()):
        self.root = self.root_factory()
        self._len = 0
        for a in arg:
            self.add(a)

    def add(self, x) -> bool:
        """
        :return: if if all went well, if an equivalent element was found in the set, it is returned instead
        """
        node = self.node_factory(x)

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
            dp.gt.add(node)
            node.lt.add(dp)
        for dc in direct_children:
            supplanted = dc.lt & node.lt
            for s in supplanted:
                s.gt.remove(dc)
            dc.lt.difference_update(supplanted)
            dc.lt.add(node)
            node.gt.add(dc)

        return True

    def _iter_nodes(self):
        seen = set()
        stack = list(self.root.gt)
        while stack:
            s = stack.pop()

            if s in seen:
                continue
            seen.add(s)
            yield s
            stack.extend(s.gt)

    def __contains__(self, item):
        return any(
            node.inner == item for node in self._iter_nodes()
        )

    def remove(self, x) -> None:
        node = next((node for node in self._iter_nodes() if node.inner == x),
                    None)
        if not node:
            raise KeyError(x)
        for p in node.lt:
            p.gt.remove(node)
            for c in node.gt:
                c.lt.discard(node)
                p.gt.add(c)
                c.lt.add(p)
        self._len -= 1

    def discard(self, x) -> None:
        try:
            self.remove(x)
        except KeyError:
            pass

    def layers(self):
        waiting: Dict[TopologicalNode, Set[TopologicalNode]] = {}
        no_prev: Iterable[TopologicalNode] = self.root.gt

        while no_prev:
            ret = []
            new_np = []
            for k in no_prev:
                ret.append(k.inner)
                for child in k.gt:
                    child_deps = waiting.get(child)
                    if child_deps is None:
                        child_deps = waiting[child] = set(child.lt)
                    child_deps.remove(k)
                    if not child_deps:
                        del waiting[child]
                        new_np.append(child)
            yield ret
            no_prev = new_np

        assert not waiting, 'cycles!'

    def __iter__(self):
        return chain.from_iterable(self.layers())

    def __len__(self):
        return self._len

    def clear(self) -> None:
        self._len = 0
        self.root.gt.clear()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        gt_factory = cls.__dict__.get('gt_factory', set)
        lt_factory = cls.__dict__.get('lt_factory', set)
        if gt_factory != set:
            rc = new_class(cls.__name__ + '_Root', (TopologicalRootNode,))
            rc.gt_factory = gt_factory
            cls.root_factory = rc
        if gt_factory != set or lt_factory != set:
            nc = new_class(cls.__name__ + '_Node', (TopologicalNode,))
            nc.gt_factory = gt_factory
            nc.lt_factory = lt_factory
            cls.node_factory = nc
