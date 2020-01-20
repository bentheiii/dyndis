# dyndis changelog
## 0.1.0: unreleased
### Internal
* candidates are no longer divided by their argument count
### Minor
* added a basic overview of how the candidates are stored
## 0.0.5: 2019-12-10
### Changed
* implementors now remove themselves from the class they are declared in
* generic alias checking method changed
* README fixed and clarifications
* ClassKeys now display as the class's name
* `dyndis.Self` is now a TypeKey
* Major changes to overload resolution
### Fixed
* typekey's inclusion test
### Added
* `MultiDispatch.classmethod`
## Enhanced
* faster topological sorting
* faster trie implementation (no recursion, less space)
## 0.0.4: 2019-11-25
### enhanced
* search now first looks up and rules out all children by MRO, then iterates over all remaining children with slower issubclass check
### added
* support for positional parameters with default values
* support for `typing.TypeVar`
* added `MultiDispatch.candidates()` method
* added `dyndis.UnboundDelegate` base class and subclasses
### changed
* `float` is now interpreted as `Union[float, int]`
* `complex` is now interpreted as `Union[float, int, complex]`
* `typing.Any` now longer evaluates to object, but rather is an inexact match to any type

## 0.0.3: 2019-11-11
### fixed
* error message for multiple candidates
### changed
* setting an implementor with a different name than the multidispatch will issue a warning
### added
* the Self type
* changed op to a regular function
* added method, and staticmethod adapters

## 0.0.2: 2019-10-31
### added
* trie improved candidate lookup
* added additional rule for least-key exclusion
* overhauled cache implementation
* RawNotImplemented
* wrote the readme
* added type handling for None, Any, ..., and NotImplemented
* allowed kwargs in MultiDispatch
### removed
* got rid of the priority alias, just number now

## 0.0.1: 2019-10-28
* initial