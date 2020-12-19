from typing import Dict, TypeVar, Generic, Tuple
from weakref import ref

V = TypeVar('V')


class WeakTupleDict(Generic[V]):
    def __init__(self):
        self.inner: Dict[Tuple[ref], V] = {}

    def __getitem__(self, item: tuple):
        t = tuple(ref(i) for i in item)
        return self.inner[t]

    def get(self, item: tuple, default=None):
        t = tuple(ref(i) for i in item)
        return self.inner.get(t, default)

    def __setitem__(self, key, value):
        def del_callback(r):
            nonlocal t
            self.inner.pop(t, None)
        t = tuple(ref(i, del_callback) for i in key)
        self.inner[t] = value

    def __len__(self):
        return len(self.inner)
