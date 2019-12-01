from typing import Dict
from unittest import TestCase

from dyndis.trie import Trie, TrieNode

import numpy as np


class TrieTest(TestCase):
    def assertNodeOk(self, node: TrieNode):
        any_value = node.has_value
        for child in node.children.values():
            any_value |= self.assertNodeOk(child)
        self.assertTrue(any_value)
        return True

    def assertTrieOk(self, trie: Trie):
        if len(trie) == 0:
            self.assertFalse(trie.root.children)
        else:
            self.assertNodeOk(trie.root)

    def assertTrieEqual(self, trie: Trie, control: Dict):
        self.assertTrieOk(trie)
        d = dict(trie.items("".join))
        self.assertEqual(len(d), len(trie))
        self.assertDictEqual(d, control)

    def test_run(self):
        ops = 1_000
        keys = ['', 'a', 'in', 'inn', 'i', 'te', 'to', 'ted', 'tea', 'ten cents']

        rem_odds = 0.15
        rolls = np.random.random_sample(ops) > rem_odds
        keys = np.random.choice(keys, size=ops)

        trie = Trie()
        ctrl = {}

        for (ins, key) in zip(rolls, keys):
            if ins:
                trie[key] = key
                ctrl[key] = key
            else:
                ans1 = trie.pop(key, None)
                ans2 = ctrl.pop(key, None)
                self.assertEqual(ans1, ans2)
            self.assertTrieEqual(trie, ctrl)
