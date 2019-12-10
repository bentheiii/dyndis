from __future__ import annotations

from itertools import product, chain
from typing import Tuple, Iterable, FrozenSet, Dict, Set
from warnings import warn

from dyndis.candidate import Candidate
from dyndis.util import Bottom


def safe_issubclass(left, right):
    """
    :return: whether left is a subclass of right, tolerant of typerrors and cyclic hierarchies
    """
    if left is object:
        # some abcs (like Hashable) result in true even when checked on object
        return right is object
    try:
        return issubclass(left, right)
    except TypeError:
        return False


def supersedes(lhs, rhs):
    """
    :return: whether a type rhs tuple is wholly contained in lhs
    """
    if lhs == rhs or len(lhs) != len(rhs):
        return False
    ret = False
    for left, right in zip(lhs, rhs):
        if ret:
            if not safe_issubclass(right, left):
                return False
        else:
            if safe_issubclass(right, left):
                if left != right:
                    ret = True
            else:
                return False
    return ret


class PossibleAmbiguity:
    """
    A possible ambiguity if the multidispatch with specific types
    """

    def __init__(self, types: Tuple[type], cands: Set[Candidate]):
        self.types = types
        self.candidates = cands

    def display(self):
        arg_types = '<' + ', '.join(t.__qualname__ for t in self.types) + '>'
        ambs = ', '.join(str(c) for c in self.candidates)
        return f'argument types {arg_types} will result in immediate ambiguities between [{ambs}]'


class Error:
    """
    A possible error if the multidispatch with a specific type
    """

    def __init__(self, type_, index, exc_type, type_vars, candidate):
        self.type = type_
        self.index = index
        self.exc_type = exc_type
        self.type_vars = type_vars
        self.candidate = candidate

    def display(self):
        if self.type_vars:
            tvtxt = f' with type variables {self.type_vars}'
        else:
            tvtxt = ''
        return f'calling with argument {self.index} = {self.type.__qualname__}{tvtxt} will raise {self.exc_type.__name__}' \
               f' from candidate {self.candidate}'


class PotentialConflictSet(Warning):
    def __init__(self, owner):
        self.owner = owner
        self.ambiguities: Dict[int, Dict[Tuple[type], Set[PossibleAmbiguity]]] = {}
        self.errors: Dict[int, Dict[type, Error]] = {}

    def add_ambiguities(self, type_sets: Iterable[FrozenSet[type]], cands: Set[Candidate]):
        max_type_sets = []
        for ts in type_sets:
            max_type_sets.append(
                [t for t in ts if not any(y != t and issubclass(t, y) for y in ts)]
            )
        for types in product(*max_type_sets):
            self._add_ambiguity(types, cands)

    def _add_ambiguity(self, types, cands):
        # check that we are not preempted by ambiguity
        immediate_cands = next(self.owner.candidates_for_types(*types))
        if len(immediate_cands) == 1:
            return

        # check that we are not preempted by an error
        for i, t in enumerate(types):
            if i not in self.errors:
                continue
            for k in self.errors[i].keys():
                if issubclass(t, k):
                    return

        # check that we are not superseded and that we don't supersede anyone else
        ambs = self.ambiguities.get(len(types))
        if ambs:
            to_clear = []
            for k in ambs.keys():
                if supersedes(types, k):
                    to_clear.append(k)
                elif supersedes(k, types):
                    return

            for tc in to_clear:
                del ambs[tc]

        ls = self.ambiguities.setdefault(len(types), {}).get(types)
        if ls:
            # join with existing ambiguities
            joined_ambs = [amb for amb in ls if not cands.isdisjoint(amb.candidates)]
            super_amb = PossibleAmbiguity(types, set.union(cands, *(amb.candidates for amb in joined_ambs)))
            ls.difference_update(joined_ambs)
            ls.add(super_amb)
        else:
            self.ambiguities[len(types)][types] = {PossibleAmbiguity(types, cands)}

    def add_error(self, ind, type_, exc_type, defined_vars, candidate):
        # check that we are not preempted by ambiguity or another callable
        type_args = [Bottom] * ind + [type_] + [Bottom] * (len(candidate.types) - ind - 1)
        try:
            immediate_cands = next(self.owner.candidates_for_types(*type_args))
        except exc_type:
            pass
        else:
            if len(immediate_cands) != 1 or immediate_cands[0] != candidate:
                return

        # check that we are not preempted by an error
        error_dict = self.errors.get(ind)
        if error_dict:
            for k in self.errors[ind].keys():
                if issubclass(type_, k):
                    return

        self.errors.setdefault(ind, {})[type_] = Error(type_, ind, exc_type, defined_vars, candidate)

    def __str__(self):
        ambs = sum(len(amb) for amb in self.ambiguities.values())
        errs = sum(len(err) for err in self.errors.values())
        if ambs:
            if errs:
                res = f'{errs} potential errors and {ambs} potential ambiguities'
            else:
                res = f'{ambs} potential ambiguities'
        elif errs:
            res = f'{errs} potential errors'
        else:
            res = 'no potential conflicts'
        return f'{self.owner} has {res}'

    def display(self):
        if not (self.ambiguities or self.errors):
            return str(self)
        return '\n'.join(
            a.display() for a in chain(
                chain.from_iterable(err.values() for err in self.errors.values()),
                chain.from_iterable(
                    chain.from_iterable(ambs.values()) for ambs in self.ambiguities.values()
                ),
            )
        )

    def __bool__(self):
        return self.errors or self.ambiguities

    def assert_(self):
        if self:
            raise self

    def warn(self):
        if self:
            warn(self)
