class AmbiguityError(RuntimeError):
    """An error indicating that a multidispatch had to decide between candidates of equal precedence"""

    def __init__(self, candidates, types):
        cands = "[" + ", ".join(str(c) for c in candidates) + "]"
        super().__init__(
            f'multiple candidates of equal precedence: {cands} for key <' + ", ".join(t.__name__ for t in types) + ">")


class NoCandidateError(TypeError):
    """An error indicating that a multidispatch has no applicable candidates, or that all candidates failed"""

    def __init__(self, args):
        super().__init__('no valid candidates for argument types <' + ", ".join(type(a).__name__ for a in args) + '>')
