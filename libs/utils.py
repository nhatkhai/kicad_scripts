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


def splitPath(path, unknown_sep=None):
  """Try to split path with difference sep style

  @return (SPLICED_PATH, SEP). SEP can be path separator or None if not
    able to detect separator style.

  @example
  >>> splitPath(r'C:\XXX\YYY\ZZZ')
  (['C:', 'XXX', 'YYY', 'ZZZ'], '\\\\')
  >>> splitPath(r'XXX')
  (['XXX'], None)
  >>> splitPath(r'/XXX/YYY/ZZZ')
  (['', 'XXX', 'YYY', 'ZZZ'], '/')
  """
  for sep in ('/', '\\'):
    test_path = path.split(sep)
    if len(test_path)>1:
      return (test_path, sep)
  return ([path], unknown_sep)


def normPath(path, curPath=None):
  """Normalize a linux or windows path

  @example
  >>> normPath(r'c:\XXX\YYY\ZZZ', r'AAA\BBB')
  'C:/XXX/YYY/ZZZ'
  >>> normPath(r'XXX\YYY\ZZZ', r'AAA/BBB')
  'AAA/BBB/XXX/YYY/ZZZ'
  >>> normPath(r'XXX', r'AAA/BBB')
  'AAA/BBB/XXX'
  >>> normPath(r'/XXX/YYY/ZZZ', r'AAA/BBB')
  '/XXX/YYY/ZZZ'
  """
  if curPath is None: 
    cwd = lambda: normPath(os.getcwd(),'')
  else: 
    cwd = lambda: curPath

  if not path:
      return cwd()

  test_path, sep = splitPath(path)

  # Check first part of this path to see if it is a relative path
  if test_path[0]=='':
    if len(test_path)>2:
      if test_path[1].lower() == 'cygdrive':
        test_path = [test_path[2].upper() + ":"] + test_path[3:]
    return os.path.sep.join(test_path)

  if test_path[0][-1]==":":
    test_path[0] = test_path[0].upper()
    return os.path.sep.join(test_path)

  test_path = os.path.sep.join(test_path)
  return os.path.normpath(os.path.join(cwd(), test_path))


def relPath(path, curPath=None):
  """Return canonical path of the specified linux or windows path

  @example
  >>> relPath(r'C:\XXX\YYY\ZZZ', r'/cygdrivE/c/XXX/BBB')
  '../YYY/ZZZ'
  >>> relPath(r'/cygdrive/c/XXX/YYY/ZZZ', r'C:\XXX\BBB')
  '../YYY/ZZZ'
  >>> relPath(r'/XXX/YYY/ZZZ', r'\XXX\BBB')
  '../YYY/ZZZ'
  """
  path = normPath(path)
  if curPath is None:
    curPath = os.getcwd()
  curPath = normPath(curPath)
  return os.path.relpath(path, curPath)


# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=False)

if __name__ == "__main__":
  tests()
