from __future__ import annotations

from functools import lru_cache

from dyndis.trie import Trie, TrieNode

_missing = object()


@lru_cache
def is_key_special(t):
    return not t.is_simple()


class RankedChildren(dict):
    """
    A dictionary that also remembers its keys that are special, and can create an exhaustion over them.
    """

    def __init__(self):
        super().__init__()
        self.special_keys = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if is_key_special(key):
            self.special_keys.add(key)

    def setdefault(self, key, *args):
        ret = super().setdefault(key, *args)
        if is_key_special(key):
            self.special_keys.add(key)
        return ret

    def __delitem__(self, key):
        super().__delitem__(key)
        self.special_keys.discard(key)

    def clear(self) -> None:
        super().clear()
        self.special_keys.clear()

    def pop(self, k, *args):
        ret = super().pop(k, *args)
        self.special_keys.discard(k)
        return ret

    popitem = copy = update = fromkeys = None

    def exhaustion(self):
        """
        :return: an exhaustion over the class's keys
        """
        return RankedChildrenExhaustion(self)


class RankedChildrenExhaustion:
    """
    An exhaustion over a RankedChildren is a data structure that supports a proxy through its internal dict,
     and also allows users to iterate over its un-exhausted, special members
    """

    def __init__(self, owner: RankedChildren):
        """
        :param owner: the owner RankedChildren
        """
        self.owner = owner
        self.unexhausted_special_keys = set(owner.special_keys)

    def exhaust(self, k, default):
        """
        Get the key's value from the owner dict, or the default if the key does not exist.
         Also marks k as exhausted if it is a special key.

        :param k: the key to search for
        :param default: the value to return if the key does not exist
        :return: the key's value, or default
        """
        self.unexhausted_special_keys.discard(k)
        return self.owner.get(k, default)

    def exhaust_many(self, keys):
        """
        Iterate over the values of the keys, skipping over missing keys. Marks all special keys as exhausted

        :param keys: the keys to iterate over
        :return: an iterable of values for the keys
        """
        valid_keys = self.owner.keys() & keys
        self.unexhausted_special_keys.difference_update(keys)
        return (self.owner[vk] for vk in valid_keys)

    def iter_unexhausted_special_items(self):
        """
        iterate over all un-exhausted special keys (and their values) in the exhaustion
        """
        for sk in self.unexhausted_special_keys:
            yield sk, self.owner[sk]


class RankedChildrenTrie(Trie):
    """
    A specialized sub-class of Trie, that uses RankedChildren for its internal children dictionary
    """

    class RankedChildrenTrieNode(TrieNode):
        children_factory = RankedChildren

    node_factory = RankedChildrenTrieNode
