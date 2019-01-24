#!/bin/python
import logging

log = logging.getLogger(__name__)

class baseLinkedData:
  """Class allow link text value from a arrays of strings

  When the value change, it change the string in the linked array
  """

  def __init__(self):
    pass

  def getValue(self):
    """
    @return the token raw value with/without quotation
    """
    raise NotImplemented("Base class method")

  def setValue(self, value):
    """ Change the token raw value
    """
    raise NotImplemented("Base class method")

  def setAndQuoteValue(self, value):
    value = value.replace('"', r'\"')
    self.setValue('"' + value + '"')

  def __str__(self):
    """
    @return the token value without any quotation
    """
    s = self.getValue()
    return s if s[0]!='"' else s[1:-1]


class linkedVirtualStrData(baseLinkedData):
  """ Allow to show fake value, but when set methods will change linked data

  @example:
  >>> for i in [1]:
  ...     a = ['abc', 'test', 'beef']
  ...     b = linkedVirtualStrData('Vir1', a, 1)
  ...     print "1", str(b)
  ...     b.setValue('ba')
  ...     print "2", a
  1 Vir1
  2 ['abc', 'ba', 'beef']
  """

  def __init__(self, string, array, index, start=0, end=None):
    baseLinkedData.__init__(self)
    self.data = array
    self.idx  = index
    self.start= start
    self.end  = end
    self.value= string

  def getValue(self):
    return self.value

  def setValue(self, value):
    if self.value == value:
      return

    s = self.data[self.idx]
    b = s[:self.start]
    if self.end:
      e = s[self.end:]
      self.end = len(value) + self.start
    else:
      e = ''
    self.data[self.idx] = b + value + e
    self.value = value


class linkedStrData(baseLinkedData):
  """
  @example:
  >>> for i in [1]:
  ...     a = ['abc', 'test', 'beef']
  ...     b = linkedStrData(a, 2)
  ...     c = linkedStrData(a, 1, 1)
  ...     print "1", str(b)
  ...     print "2", str(c)
  ...     c.setValue('jomm')
  ...     print "3", a
  ...     b.setAndQuoteValue('ba')
  ...     print "4", a
  1 beef
  2 est
  3 ['abc', 'tjomm', 'beef']
  4 ['abc', 'tjomm', '"ba"']
  """

  def __init__(self, array, index, start=0, end=None):
    baseLinkedData.__init__(self)
    self.data = array
    self.idx  = index
    self.start= start
    self.end  = end

  def getValue(self):
    return self.data[self.idx][self.start:self.end]

  def setValue(self, value):
    s = self.data[self.idx]
    b = s[:self.start]
    if self.end:
      e = s[self.end:]
      self.end = len(value) + self.start
    else:
      e = ''
    self.data[self.idx] = b + value + e


#
# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  tests()
