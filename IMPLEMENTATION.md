Here we will explain how candidates are stored within a `MultiDispatch`

* All candidates are stored in a topological set. A `TopologicalSet` is a set of candidates ordered such that we can quickly extract all the candidates by layer.
    * currently, TopologicalSet does not support removal, but for now it is unnecessary as candidates cannot be removed from a `MultiDispatch`.

* Finally, each layer in the `TopologicalSet` is stored as a `Trie` of candidates, ordered by their parameter types. This allows for efficient lookup for specific types.