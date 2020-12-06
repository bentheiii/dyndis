from pytest import raises

from dyndis.trie import Trie


def test_empty():
    t = Trie()
    assert set(t.keys()) == set()
    assert t.root.value(None) is None
    with raises(ValueError):
        t.root.value()


def test_keys():
    t = Trie()
    t['one'] = 1
    t['two'] = 2
    assert set(t.keys()) == {tuple('one'), tuple('two')}


def test_clear():
    t = Trie({
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3
    })
    assert set(t.values()) == set(range(4))
    t.clear()
    assert not t


def test_get():
    t = Trie({
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3
    })
    assert t.get('one') == t['one'] == 1
    assert t.get('ten', 10) == 10
    assert t.get('t', 12) == 12
    with raises(KeyError):
        x = t['t']


def test_set_default():
    t = Trie({
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3
    })
    assert t.setdefault('zero', None) == 0
    assert t['zero'] == 0
    assert t.setdefault('four', 4) == 4
    assert t['four'] == 4


def test_pop():
    t = Trie({
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3
    })
    assert t.pop('zero', None) == 0
    assert 'zero' not in t
    assert t.pop('zero', None) is None
    with raises(KeyError):
        assert t.pop('zero')


def test_items():
    t = Trie({
        'zero': 0,
        'one': 1,
        'two': 2,
        'three': 3
    })
    items = t.items(None)
    joined = {''.join(k) for (k,_) in items}
    assert joined == {'zero', 'one', 'two', 'three'}
