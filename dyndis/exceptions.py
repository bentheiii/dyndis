class AmbiguityError(RuntimeError):
    """An error indicating that a multidispatch had to decide between candidates of equal precedence"""

    def __init__(self, candidates, types):
        cands = "[" + ", ".join(str(c) for c in candidates) + "]"
        super().__init__(
            f'multiple candidates of equal precedence: {cands} for key <' + ", ".join(t.__name__ for t in types) + ">")


class NoCandidateError(TypeError):
    """An error indicating that a multidispatch has no applicable candidates"""

    def __init__(self, args):
        super().__init__('no valid candidates for argument types <' + ", ".join(type(a).__name__ for a in args) + '>')


class AmbiguousBindingError(RuntimeError):
    """An error indicating that a type variable could not find a single type to bind to"""

    def __init__(self, typevar, subclass, unrelated_classes):
        super().__init__(f'type variable {typevar} must up-cast type {subclass} to one of its constrained types,'
                         f' but it is a subclass of multiple non-related constraints: {unrelated_classes}'
                         f' (consider adding {subclass} as an explicit constraint in {typevar},'
                         f' or a specialized overload for {subclass})')


class UnboundTypeVar(RuntimeError):
    def __init__(self, typevar, unbound):
        super().__init__(f'type variable {typevar} must be bound before {unbound}')
