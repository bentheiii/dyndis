from collections import defaultdict
from typing import TypeVar, Iterable, Iterator, Set

T = TypeVar('T')


def topological_sort(members: Iterable[T]) -> Iterator[Set[T]]:
    dependencies = {}
    dependants = defaultdict(set)
    next_layer = set()
    for a in members:
        d = set()
        for b in members:
            if a.envelops(b):
                d.add(b)
                dependants[b].add(a)
        if d:
            dependencies[a] = d
        else:
            next_layer.add(a)

    yield next_layer

    while dependencies:
        new_layer = set()
        for done in next_layer:
            for freed in dependants[done]:
                dependencies[freed].remove(done)
                if not dependencies[freed]:
                    dependencies.pop(freed)
                    new_layer.add(freed)
        if not new_layer:
            raise RuntimeError('cycle')
        next_layer = new_layer
        yield next_layer
