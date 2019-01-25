#!/usr/bin/python
import logging


log = logging.getLogger(__name__)


def MapNestedDict(data, func):
  """Map a nested dictionary with specified func

  @example:
  >>> a                      = {"a": {"b": 1 , "c": 2 }, "d": 3 }
  >>> MapNestedDict(a, str) == {'a': {'b':'1', 'c':'2'}, 'd':'3'}
  True
  """
  if not isinstance(data, dict):
    return func(data)

  return {k:MapNestedDict(e, func) for k, e in data.items()}


def MapNestedList(data, func):
  """Map a nested dictionary with specified func

  @example:
  >>> a                      = [ 1 , [ 2 ,  3 ],  4 ]
  >>> MapNestedList(a, str)
  ['1', ['2', '3'], '4']
  """
  if not isinstance(data, list):
    return func(data)

  return [MapNestedList(e, func) for e in data]

# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  tests()
