# dyndis changelog
## 0.0.4: unreleased
### enhanced
* search now first looks up and rules out all children by MRO, then iterates over all remaining children with slower issubclass check
### added
* support for positional parameters with default values
* support for `typing.TypeVar`
* added `MultiDispatch.candidates()` method
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