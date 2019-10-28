from functools import partial
from itertools import chain
from numbers import Number
from typing import NamedTuple, Callable, List, Union

from dyndis.candidate import Candidate


class QueuedImplementation(NamedTuple):
    priority: Number
    func: Callable
    permutations: bool

    def cands(self, owner):
        ret = Candidate.from_func(self.priority, self.func, fallback_type_hint=owner)
        if self.permutations:
            ret = chain.from_iterable(r.permutations() for r in ret)
        return ret


class Implementor:
    def __init__(self, multidispatch):
        self.multidispatch = multidispatch

        self.queue: List[QueuedImplementation] = []
        self.locked = False

    def __set_name__(self, owner, name):
        if self.locked:
            return
        self.multidispatch.add_candidates(chain.from_iterable(q.cands(owner) for q in self.queue))
        self.locked = True

    def implementor(self, priority=0, symmetric=False, func=None) \
            -> Union[Callable[..., 'Implementor'], 'Implementor']:
        if not func:
            return partial(self.implementor, priority, symmetric)

        if self.locked:
            raise Exception('the implementor has already been locked, no new functions can be added')
        self.queue.append(QueuedImplementation(priority=priority, func=func, permutations=symmetric))
        return self
