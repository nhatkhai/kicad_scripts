#!/usr/bin/python
import os
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


def normPath(path, curPath=None):
  # Normalize path that can be either from Windows/Linux style
  # By first check if any "/" character in the path
  test_path = path.split("/")

  if len(test_path)==0:
  # Look like is it windows path, so we split it in Window way
    test_path = path.split("\\")

  # Check first part of this path to see if it is a relative path
  if test_path[0] in {'..', '.'} and test_path[0][-1]!=":":
    if not curPath: 
        curPath = os.getcwd()
    return os.path.normpath(os.path.join(curPath, path))
  else:
    return os.path.sep.join(test_path)


# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  tests()
