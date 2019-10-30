from typing import Dict
from unittest import TestCase

from dyndis.trie import Trie

import numpy as np


class TrieTest(TestCase):
    def assertTrieOk(self, trie: Trie):
        tot = int(trie.has_value())
        for child in trie.children.values():
            self.assertGreater(len(child), 0)
            self.assertTrieOk(child)
            tot += len(child)
        self.assertEqual(tot, len(trie))

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
