from __future__ import annotations

from types import MappingProxyType
from typing import TypeVar, Generic, Dict, Tuple, Iterable, Iterator, MutableMapping, List, Callable, Any, Optional

K = TypeVar('K')
V = TypeVar('V')

_missing = object()
_no_default = object()


class Trie(Generic[K, V], MutableMapping[Iterable[K], V]):
    _empty_val: V
    _len: int

    def __init__(self):
        self._children: Dict[K, Trie[K, V]] = {}
        self.children = MappingProxyType(self._children)

        self.clear()

    def _set_default_child(self, k):
        ret = self._children.get(k, None)
        if ret is None:
            ret = self._children[k] = type(self)()
        return ret

    def _set(self, i: Iterator[K], v: V, override: bool):
        # return 2-tuple: the change in lens, the current value for the key
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
        try:
            n = next(i)
        except StopIteration:
            return self.value(d)
        else:
            child = self._children.get(n)
            if not child:
                return d
            return child._get(i, d)

    def _pop(self, i: Iterator[K]):
        # returns a 3-tuple: whether an item was found, the child key the item was found in if it empty,
        #   and the value of the item
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
            child = self._children.get(n)
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
                del self._children[n]

            return True, _missing, popped

    def _pop_item(self, buffer: List[K]):
        if self._empty_val is not _missing:
            ret = self._empty_val
            self._empty_val = _missing
            self._len -= 1
            return ret

        t: Trie
        k, t = next(iter(self._children.items()))
        buffer.append(k)
        ret = t._pop_item(buffer)
        self._len -= 1
        if not t:
            if self or not buffer:
                del self._children[k]
        return ret

    def _items(self):
        buffer = []
        if self._empty_val is not _missing:
            yield buffer, self._empty_val
        stack: List[Iterator[Tuple[K, Trie[K, V]]]] = [iter(self._children.items())]
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
                stack.append(iter(t._children.items()))

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
        if key_joiner:
            return (key_joiner(k) for k, _ in self._items())
        else:
            return (k for k, _ in self._items())

    def items(self, key_joiner: Optional[Callable[[List], Any]] = tuple):
        if key_joiner:
            return ((key_joiner(k), v) for k, v in self._items())
        else:
            return ((k, v) for k, v in self._items())

    def values(self):
        if self._empty_val is not _missing:
            yield self._empty_val
        for c in self._children.values():
            yield from c.values()

    def get(self, k, default=None):
        return self._get(iter(k), default)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return len(self) == len(other) \
               and self._empty_val == other._empty_val \
               and self._children == other._children

    def pop(self, key, default=_no_default):
        success, child_key, ret = self._pop(iter(key))
        if not success:
            if default is _no_default:
                raise KeyError(key)
            return default
        if child_key is not _missing:
            # a 0-length child needs dropping
            assert len(self._children[child_key]) == 0
            del self._children[child_key]
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
        self._children.clear()

    def setdefault(self, k, default=None):
        return self._set(iter(k), default, override=False)[1]

    def value(self, default=_no_default):
        ret = self._empty_val
        if ret is _missing:
            if default is _no_default:
                raise KeyError()
            return default
        return ret

    def has_value(self):
        return self._empty_val is _missing
