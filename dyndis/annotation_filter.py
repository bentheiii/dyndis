from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping, TypeVar, Union, FrozenSet, Any

try:
    from typing import TypedDict
except ImportError:
    TYPED_DICT_META = None
else:
    TYPED_DICT_META = type(TypedDict('blank', {}))
    del TypedDict


def is_type_like(t):
    try:
        isinstance(None, t)
    except TypeError:
        return False
    return True


def annotation_filter(x):
    if TYPED_DICT_META and isinstance(x, TYPED_DICT_META):
        raise TypeError('cannot use a Typed Dict as a multidispatch annotation')

    if is_type_like(x):
        return ClassAnnotationFilter(x)
    if x in (None, ..., NotImplemented):
        return annotation_filter(type(x))
    if x is Any:
        return AnyAnnotationFilter
    if isinstance(x, TypeVar):
        if x.__constraints__:
            return ConstrainedTypeVarAnnotatedFilter(x)
        return BoundedTypeVarAnnotatedFilter(x)

    origin = getattr(x, '__origin__', None)
    if origin is Union:
        args = frozenset(annotation_filter(a) for a in x.__args__)
        return UnionAnnotationFilter(args)

    raise TypeError(x)


class AnnotationFilter(ABC):
    @abstractmethod
    def match(self, x: type, defined: Mapping[TypeVar, AnnotationFilter]) \
            -> Union[bool, Mapping[TypeVar, AnnotationFilter]]:
        pass

    @abstractmethod
    def envelops(self, other: AnnotationFilter) -> bool:
        """
        `self` envelops `other` if, for any defined mapping `d` and type 't',
         `self.match(t, d) or not other.match(t, d)`
        """
        return other.enveloped_by(self)

    def enveloped_by(self, other: AnnotationFilter) -> bool:
        raise TypeError

    @abstractmethod
    def __str__(self):
        pass


class ClassAnnotationFilter(AnnotationFilter):
    def __init__(self, cls: type):
        self.cls = cls

    def match(self, x, defined: Mapping[TypeVar, AnnotationFilter]):
        return issubclass(x, self.cls)

    def envelops(self, other: AnnotationFilter) -> bool:
        if isinstance(other, ClassAnnotationFilter):
            return issubclass(other.cls, self.cls)
        return super().envelops(other)

    def __str__(self):
        return self.cls.__name__

    def __eq__(self, other):
        return type(self) == type(other) and self.cls == other.cls

    def __hash__(self):
        return hash(self.cls)


class UnionAnnotationFilter(AnnotationFilter):
    def __init__(self, args: FrozenSet[AnnotationFilter]):
        self.args = args

    def match(self, x, defined: Mapping[TypeVar, AnnotationFilter]):
        results = (a.match(x, defined) for a in self.args)
        first_truish = False
        for r in results:
            if r is True:
                if first_truish is True:
                    continue
                elif not first_truish:
                    first_truish = True
                else:
                    raise TypeError(f'cannot match {x} to Union due to conflicting results')
            elif r:
                if first_truish:
                    raise TypeError(f'cannot match {x} to Union due to conflicting results')
                first_truish = r
        return first_truish

    def envelops(self, other: AnnotationFilter) -> bool:
        if isinstance(other, ClassAnnotationFilter):
            return any(a.envelops(other) for a in self.args)
        if isinstance(other, UnionAnnotationFilter):
            return all(self.envelops(a) for a in other.args)
        return super().envelops(other)

    def enveloped_by(self, other: AnnotationFilter) -> bool:
        if isinstance(other, ClassAnnotationFilter):
            return all(other.envelops(a) for a in self.args)
        return super().enveloped_by(other)

    def __eq__(self, other):
        return type(self) == type(other) and self.args == other.args

    def __hash__(self):
        return hash(self.args)

    def __str__(self):
        return '(' + "|".join(str(i) for i in self.args) + ")"


class TypeVarAnnotationFilter(AnnotationFilter):
    def __init__(self, tv: TypeVar):
        self.tv = tv

    @abstractmethod
    def match(self, x, defined: Mapping[TypeVar, AnnotationFilter]) -> Union[bool, Mapping[TypeVar, AnnotationFilter]]:
        already_defined = defined.get(self.tv)
        if already_defined:
            return already_defined.match(x, defined)

    def __eq__(self, other):
        return type(self) == type(other) and self.tv == other.tv

    def __hash__(self):
        return hash(self.tv)

    def __str__(self):
        return '~' + self.tv.__name__


class ConstrainedTypeVarAnnotatedFilter(TypeVarAnnotationFilter):
    def __init__(self, tv: TypeVar):
        super().__init__(tv)
        self.constraints = [annotation_filter(c) for c in tv.__constraints__]

    def match(self, x, defined: Mapping[TypeVar, AnnotationFilter]) -> Union[bool, Mapping[TypeVar, AnnotationFilter]]:
        s = super().match(x, defined)
        if s is not None:
            return s
        matches = list(filter(lambda t: t[1], ((af, af.match(x, defined)) for af in self.constraints)))
        if not matches:
            return False
        if len(matches) == 1:
            af, match = matches[0]
            if match is True:
                return {self.tv: af}
            return {**match, self.tv: af}
        raise TypeError(f'ambiguous typevar match, value {x} matched {", ".join(a for (a, _) in matches)}')

    def envelops(self, other: AnnotationFilter) -> bool:
        return self == other or all(c.envelops(other) for c in self.constraints)

    def enveloped_by(self, other: AnnotationFilter) -> bool:
        return self == other or all(other.envelops(c) for c in self.constraints)


class BoundedTypeVarAnnotatedFilter(TypeVarAnnotationFilter):
    def __init__(self, tv: TypeVar):
        super().__init__(tv)
        self.bound = annotation_filter(tv.__bound__ or object)

    def match(self, x, defined: Mapping[TypeVar, AnnotationFilter]) -> Union[bool, Mapping[TypeVar, AnnotationFilter]]:
        s = super().match(x, defined)
        if s is not None:
            return s
        sub_match = self.bound.match(x, defined)
        if sub_match is True:
            return {self.tv: annotation_filter(x)}
        elif sub_match:
            return {**sub_match, self.tv: annotation_filter(x)}
        return False

    def envelops(self, other: AnnotationFilter) -> bool:
        return self == other

    def enveloped_by(self, other: AnnotationFilter) -> bool:
        return self == other or other.envelops(self.bound)


class _AnyAnnotationFilter(AnnotationFilter):
    def match(self, x: type, defined: Mapping[TypeVar, AnnotationFilter]):
        return True

    def envelops(self, other: AnnotationFilter) -> bool:
        return True

    def enveloped_by(self, other: AnnotationFilter) -> bool:
        return other is self

    def __str__(self):
        return 'Any'


AnyAnnotationFilter = _AnyAnnotationFilter()
