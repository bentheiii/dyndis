from __future__ import annotations

from functools import lru_cache
from typing import Any

from dyndis.trie import Trie

_missing = object()
object_subclass_check = type(object).__subclasscheck__


@lru_cache
def is_key_special(t):
    """
    a key is considered special if all its classes will have in their MRO()

    >>> is_key_special(int)
    False
    >>> is_key_special(bool)
    False
    >>> class A: pass
    >>> is_key_special(A)
    False
    >>> from collections.abc import Iterable
    >>> is_key_special(Iterable)
    True
    >>> from abc import ABC
    >>> class B(ABC): pass
    >>> is_key_special(B)
    True
    """
    return not (isinstance(t, type) and type(t).__subclasscheck__ is object_subclass_check)


class RankedChildren(dict):
    def __init__(self):
        super().__init__()
        self.special_keys = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if is_key_special(key):
            self.special_keys.add(key)

    def __delitem__(self, key):
        super().__delitem__(key)
        self.special_keys.discard(key)

    def pop(self, k, *args):
        ret = super().pop(k, *args)
        self.special_keys.discard(k)
        return ret

    def exhaustion(self):
        return RankedChildrenExhaustion(self)


class RankedChildrenExhaustion:
    def __init__(self, owner: RankedChildren):
        self.owner = owner
        self.special_keys = set(owner.special_keys)

    def pops(self, keys):
        valid_keys = self.owner.keys() & keys
        self.special_keys.difference_update(keys)
        return (self.owner[vk] for vk in valid_keys)

    def pop(self, k, default=_missing):
        self.special_keys.discard(k)
        if default is _missing:
            return self.owner[k]
        return self.owner.get(k, default)

    def iter_special_items(self):
        for sk in self.special_keys:
            yield sk, self.owner[sk]


class RankedChildrenTrie(Trie):
    children_factory = RankedChildren
