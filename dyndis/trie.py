from __future__ import annotations

from typing import TypeVar, Generic, Iterable, MutableMapping, Callable, List, Any

K = TypeVar('K')
V = TypeVar('V')

_blank = object()
_no_default = object()

# todo make index-invariant queries?

class TrieNode(Generic[K, V]):
    """
    A node for a trie
    """
    __slots__ = 'children', 'inner_value'

    def __init__(self):
        self.children: MutableMapping[K, TrieNode[K, V]] = {}
        self.inner_value: V = _blank

    def value(self, default=_no_default):
        """
        :return: the inner value of the node, or default if none exists
        """
        if self.inner_value is _blank:
            if default is _no_default:
                raise ValueError('no value')
            return default
        return self.inner_value

    @property
    def has_value(self):
        """
        :return: whether the node has an inner value
        """
        return self.inner_value is not _blank

    def values(self, buffer: list):
        """
        iterate over the values of the node and its children
        :param buffer: a key buffer to store the sub-keys visited up to the current value
        """
        if self.has_value:
            yield self.value()
        for k, v in self.children.items():
            buffer.append(k)
            yield from v.values(buffer)
            buffer.pop()

    def clear(self):
        self.children.clear()
        self.inner_value = _blank

    def ensure_child(self, sub_key: K) -> TrieNode[K, V]:
        """
        make sure a node has a child of the sub-key, and return it
        """
        ret = self.children.get(sub_key)
        if not ret:
            ret = self.children[sub_key] = TrieNode()
        return ret


class Trie(Generic[K, V], MutableMapping[Iterable[K], V]):
    """
    A Trie that can iterate over nodes
    """

    def __init__(self, update_arg=None, **kwargs):
        self.root: TrieNode[K, V] = TrieNode()
        self._len = 0
        if update_arg or kwargs:
            self.update(update_arg, **kwargs)

    def get(self, key: Iterable[K], default: V = None) -> V:
        current = self.root
        for k in key:
            current = current.children.get(k)
            if not current:
                return default
        ret = current.inner_value
        if ret is _blank:
            return default
        return ret

    def __getitem__(self, item):
        ret = self.get(item, _blank)
        if ret is _blank:
            raise KeyError(item)
        return ret

    def _set(self, key, value, override):
        current = self.root
        for k in key:
            current = current.ensure_child(k)
        current_value = current.inner_value
        if current_value is _blank:
            self._len += 1
        elif not override:
            return current_value
        current.inner_value = value
        return value

    def __setitem__(self, key, value):
        return self._set(key, value, True)

    def setdefault(self, key, default=None):
        return self._set(key, default, False)

    def pop(self, key, default: V = _no_default):
        stack = [(None, self.root)]
        for k in key:
            current = stack[-1][-1].children.get(k)
            if not current:
                break
            stack.append((k, current))
        else:
            current = stack[-1][-1]
            ret = current.inner_value
            if ret is not _blank:
                current.inner_value = _blank
                self._len -= 1
                clear_flag = False
                clear_flag_key = None
                for k, s in reversed(stack):
                    if clear_flag:
                        del s.children[clear_flag_key]
                        clear_flag = False

                    if s.inner_value is _blank and not s.children:
                        clear_flag = True
                        clear_flag_key = k
                return ret

        if default is _no_default:
            raise KeyError(key)

        return default

    def __delitem__(self, key):
        return self.pop(key)

    def _items(self):
        """
        iterate over the key-value pairs in the trie
        note: the keys returned are all returned using the same list buffer, they must be copied or
         converted before returning to the user
        """
        buffer = []
        for v in self.root.values(buffer):
            yield buffer, v

    def __len__(self):
        return self._len

    def __iter__(self, key_converter=tuple):
        return (k for (k, _) in self.items(key_converter))

    def items(self, key_converter: Callable[[List[K]], Any] = tuple):
        if key_converter:
            return ((key_converter(k), v) for (k, v) in self._items())
        return ((k, v) for (k, v) in self._items())

    def values(self):
        return self.root.values([])

    def clear(self):
        self.root.clear()
        self._len = 0
