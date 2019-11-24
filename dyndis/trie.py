from __future__ import annotations

from types import MappingProxyType
from typing import TypeVar, Generic, Dict, Tuple, Iterable, Iterator, MutableMapping, List, Callable, Any, Optional

K = TypeVar('K')
V = TypeVar('V')

_missing = object()
_no_default = object()


class Trie(Generic[K, V], MutableMapping[Iterable[K], V]):
    """
    A generic non-compressing trie that supports manual search. Acts as a mapping of iterables to keys
    """
    _empty_val: V
    _len: int

    children_factory = dict

    def __init__(self, map=(), **additionals):
        self.children: Dict[K, Trie[K, V]] = self.children_factory()

        self.clear()

        self.update(map, **additionals)

    def _set_default_child(self, k):
        """
        ensure the trie has a child for key k, and returns it
        :param k: the key to ensure a child exists for
        :return: the child for key k
        """
        ret = self.children.get(k, None)
        if ret is None:
            ret = self.children[k] = type(self)()
        return ret

    def _set(self, i: Iterator[K], v: V, override: bool):
        """
        Set a value in the trie
        :param i: an iterator of keys for the trie and its children
        :param v: the value to set for the key
        :param override: whether to destroy an existing key
        :return: 2-tuple: the change in lens, the current value for the key
        """
        try:
            n = next(i)
        except StopIteration:
            if self._empty_val is _missing:
                delta = 1
                val = self._empty_val = v
                self._len += 1
            else:
                delta = 0
                if override:
                    val = self._empty_val = v
                else:
                    val = self._empty_val
            return delta, val
        else:
            child = self._set_default_child(n)
            delta, val = child._set(i, v, override)
            self._len += delta
            return delta, val

    def _get(self, i: Iterator[K], d: V):
        """
        Get the value in a trie
        :param i: an iterator of keys for the trie and its children
        :param d: the default value to return if the value does not exist
        :return: the value of the trie of the final key, or d if none exists
        """
        try:
            n = next(i)
        except StopIteration:
            return self.value(d)
        else:
            child = self.children.get(n)
            if not child:
                return d
            return child._get(i, d)

    def _pop(self, i: Iterator[K]):
        """
        Remove a key and its value from the trie, will delete empty child tries
        :param i: an iterator of keys for the trie and its children
        :return: a 3-tuple: whether an item was found,
         the child key the item was found in if it empty,
         and the value of the item
        """
        try:
            n = next(i)
        except StopIteration:
            if self._empty_val is _missing:
                return False, None, None
            else:
                self._len -= 1
                popped = self._empty_val
                self._empty_val = _missing
                return True, _missing, popped
        else:
            child = self.children.get(n)
            if not child:
                return False, None, None
            success, _, popped = child._pop(i)
            if not success:
                return False, None, None
            self._len -= 1
            if self._len == 0:
                # don't bother dropping children, since you're gonna get dropped anyway, return the key needed to drop
                return True, n, popped

            if len(child) == 0:
                del self.children[n]

            return True, _missing, popped

    def _pop_item(self, buffer: List[K]):
        """
        Remove a key-value pair from the trie via DFS, will delete empty child tries
        :param buffer: a list containing the complete key of the deleted pair
        :return: the value deleted
        """
        if self._empty_val is not _missing:
            ret = self._empty_val
            self._empty_val = _missing
            self._len -= 1
            return ret

        t: Trie
        k, t = next(iter(self.children.items()))
        buffer.append(k)
        ret = t._pop_item(buffer)
        self._len -= 1
        if not t:
            if self or not buffer:
                del self.children[k]
        return ret

    def _items(self):
        """
        Iterate over all key-value pairs in the trie an its children (using DFS)
        Warning: each is returned using the same key buffer, convert to list or other sequency type
         prior to returning to user
        """
        buffer = []
        if self._empty_val is not _missing:
            yield buffer, self._empty_val
        stack: List[Iterator[Tuple[K, Trie[K, V]]]] = [iter(self.children.items())]
        while stack:
            last_iter = stack[-1]
            try:
                k, t = next(last_iter)
            except StopIteration:
                stack.pop()
                if not stack:
                    return
                buffer.pop()
                continue
            else:
                buffer.append(k)
                if t._empty_val is not _missing:
                    yield buffer, t._empty_val
                stack.append(iter(t.children.items()))

    def __setitem__(self, string: Iterable[K], value: V):
        self._set(iter(string), value, True)

    def __getitem__(self, item):
        ret = self._get(iter(item), _missing)
        if ret is _missing:
            raise KeyError(item)
        return ret

    def __len__(self):
        return self._len

    def __delitem__(self, key):
        self.pop(key)

    def __iter__(self):
        return self.keys(tuple)

    def __contains__(self, item):
        return self._get(iter(item), _missing) is not _missing

    def keys(self, key_joiner: Optional[Callable[[List], Any]] = tuple):
        """
        get an iterable of keys
        :param key_joiner: an optional function to convert the key-buffer to permanent data (default is tuple)
        """
        if key_joiner:
            return (key_joiner(k) for k, _ in self._items())
        else:
            return (k for k, _ in self._items())

    def items(self, key_joiner: Optional[Callable[[List], Any]] = tuple):
        """
        get an iterable of key-value pairs
        :param key_joiner: an optional function to convert the key-buffer to permanent data (default is tuple)
        """

        if key_joiner:
            return ((key_joiner(k), v) for k, v in self._items())
        else:
            return ((k, v) for k, v in self._items())

    def values(self):
        if self._empty_val is not _missing:
            yield self._empty_val
        for c in self.children.values():
            yield from c.values()

    def get(self, k, default=None) -> V:
        return self._get(iter(k), default)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return len(self) == len(other) \
               and self._empty_val == other._empty_val \
               and self.children == other.children

    def pop(self, key, default=_no_default):
        success, child_key, ret = self._pop(iter(key))
        if not success:
            if default is _no_default:
                raise KeyError(key)
            return default
        if child_key is not _missing:
            # a 0-length child needs dropping
            assert len(self.children[child_key]) == 0
            del self.children[child_key]
        return ret

    def popitem(self, key_joiner: Optional[Callable[[List], Any]] = tuple):
        if not self:
            raise KeyError
        buffer = []
        v = self._pop_item(buffer)
        if buffer:
            first = buffer[0]
            if not self.children[first]:
                del self.children[first]
        if key_joiner not in (None, list):
            key = key_joiner(buffer)
        else:
            key = buffer
        return key, v

    def clear(self):
        self._len = 0
        self._empty_val = _missing
        self.children.clear()

    def setdefault(self, k, default=None):
        return self._set(iter(k), default, override=False)[1]

    def value(self, default=_no_default):
        """
        Get the current internal value of the trie, equivelant to `self[()]`
        :param default: the optional value to return if a the trie has no value, by default, will raise KeyError
        """
        ret = self._empty_val
        if ret is _missing:
            if default is _no_default:
                raise KeyError()
            return default
        return ret

    def has_value(self):
        """
        :return: whether the trie has in internal value, equivelant to `() in self`
        """
        return self._empty_val is not _missing
