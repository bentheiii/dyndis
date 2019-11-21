from functools import partial
from itertools import chain
from numbers import Number
from typing import NamedTuple, Callable, List, Union
from warnings import warn

from dyndis.candidate import Candidate, Self


class QueuedImplementation(NamedTuple):
    """
    An implementation inside a class that is waiting for the class to complete its creation
    """
    priority: Number
    func: Callable
    permutations: bool

    def cands(self, owner):
        """
        create a set of candidates when the class is complete
        """
        ret = Candidate.from_func(self.priority, self.func, fallback_type_hint=Self, self_type=owner)
        if self.permutations:
            ret = chain.from_iterable(r.permutations() for r in ret)
        return ret


class Implementor:
    """
    A descriptor that holds candidates that include a class until it is complete
    """

    def __init__(self, multidispatch):
        """
        :param multidispatch: the multidispatch to add the candidates to
        """
        self.multidispatch = multidispatch

        self.queue: List[QueuedImplementation] = []
        self.locked = False

    def __set_name__(self, owner, name):
        """
        indicates that the class is fully created, adds the queued implementors to the multidispatch
        """

        def check_candidate(candidate):
            if self.multidispatch.__name__ is not None \
                    and candidate.__name__ is not None\
                    and self.multidispatch.__name__.strip('_') != candidate.__name__.strip('_'):
                warn(f'implementor {candidate} in class {owner.__name__} has dissimilar name from multidispatch {self.multidispatch}', stacklevel=5)
            return candidate

        if self.locked:
            return
        self.multidispatch.add_candidates(
            check_candidate(c) for c in
            chain.from_iterable(q.cands(owner) for q in self.queue)
        )
        self.locked = True

    def implementor(self, priority=0, symmetric=False, func=None) \
            -> Union[Callable[..., 'Implementor'], 'Implementor']:
        """
        Add a new queued candidate, usable as a decorator
        :param priority: the priority of the candidate
        :param symmetric: if set to true, all the permutations of the candidate will also be added
        :param func: the function to be added
        """
        if not func:
            return partial(self.implementor, priority, symmetric)

        if self.locked:
            raise Exception('the implementor has already been locked, no new functions can be added')
        self.queue.append(QueuedImplementation(priority=priority, func=func, permutations=symmetric))
        return self
