#!/bin/python
"""
    @package
    Update eeschema symbol files from CSV BOM list.
"""
import sys
import os
import csv
import re
import logging
from Queue import Queue

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

from libs import eeschematic
from libs import utils

log = logging.getLogger(__name__)


# Special BOM Header
ITEM          = 'item'         
QUANTITY      = 'quantity'     
POPULATE      = 'populate'
REFERENCE     = 'reference'    
VALUE         = 'value'        
SYMBOL        = 'symbol'       
FOOTPRINT     = 'footprint'    
DATASHEET     = 'datasheet'    
MANUFACTURER  = 'manufacturer' 
PARTNUM       = 'partnum'      
SUPPLIER      = 'supplier'     
SUPPLIERNUM   = 'suppliernum'  
PRICE         = 'price'        


# Special meta data
SCHFILE      = 'schfile'


class bom:
  def __init__(self):
    self.meta = {} # META_KEY -> [VALUE]
    self.header={} # HEADER_ID -> ( COLUMN_INDEX
                   #              , COLUMN_NAME
                   #              , TRUE_OF_SPECIAL_COLUMN )
    self.refs = {} # REFERENCE -> { HEADER_ID -> value }

  def getSchFileName(self):
    return self.meta.get(SCHFILE, [None])[0]

  def getHeaderTexts(self):
    return {k:v[1] for k, v in self.header.iteritems()}

  def genColNameToHeaderID(self):
    return {fieldName:colID 
        for colID, (colIdx, fieldName, special) in self.header.items()}

  def getReferences(self):
    return self.refs

  @staticmethod
  def getAllReferences(refs):
    """ Return array of reference split out from the refs string

    @example: 
    >>> csv_bom.getAllReferences('C1-C4  ,  C21; C23.4,C25..C27')
    ['C1', 'C2', 'C3', 'C4', 'C21', 'C23.4', 'C25', 'C26', 'C27']
    """
    refNum= 0
    state = ""
    allref = []
    for m in csv_bom.getAllReferences_re.finditer(refs):
      #log.debug("MATCH: %s", m.groups())

      if m.group(4):
        allref.append(m.group(1))
        state = ""
        continue

      if m.group(4) is None:
        nextRefNum = int(m.group(3))+1
        if state in {"-", ".."}:
          for i in range(refNum, nextRefNum):
            allref.append(m.group(2) + str(i)) 
        else:
          allref.append(m.group(1)) 

        refNum = nextRefNum
        state  = m.group(5)

    return allref

  # TODO: Move below class methods to output process code where it belong
  def transformToSch(self, references):
    """Combine supplier, price, and part number into once supplier field
    """
    for ref in references:
      values = self.refs.get(ref, {})
      values[SUPPLIER] = ":".join([a for a in (
          values.pop(k, None) for k in (SUPPLIER, SUPPLIERNUM, PRICE))
          if a is not None])

      dnp_values = {'DO NOT POPULATE'}
      for k in (VALUE, POPULATE):
        if values.get(k, '').upper() in dnp_values:
          values[k] = "DNP"

  def joinValues4Refs(self, references):
    """
    @param references: a collection of references
    """
    values = [self.refs.get(ref,{}) for ref in references]
    values, joinedFields = bom._join2Dict(values)
    joinedFields -= {REFERENCE}
    for ref in references: 
      self.refs[ref] = values
    return values, joinedFields

  @staticmethod
  def _join2Dict(dicts, sep="; "):
    keys = set()
    for d in dicts: keys.update(d.keys())

    new = {}
    joinedFields = set()
    for key in keys:
      val = set((d.get(key) for d in dicts))
      val -= {None}
      if len(val)>1:
        joinedFields.add(key)
      new[key] = sep.join(val)

    return new, joinedFields


class csv_bom(bom):
  HEADER_NAMES = re.compile(
      '(?P<'+ITEM        +'>' 'Item#?'                              ')$|'
      '(?P<'+QUANTITY    +'>' 'Qty|Qnty|Quantity'                   ')$|'
      '(?P<'+POPULATE    +'>' 'Pop(ulate|ulation)?'                 ')$|'
      '(?P<'+REFERENCE   +'>' 'Ref|Reference.*'                     ')$|'
      '(?P<'+VALUE       +'>' 'Value'                               ')$|'
      '(?P<'+SYMBOL      +'>' 'Libpart|Part|Library.*'              ')$|'
      '(?P<'+FOOTPRINT   +'>' 'Footprint'                           ')$|'
      '(?P<'+DATASHEET   +'>' 'Datasheet'                           ')$|'
      '(?P<'+MANUFACTURER+'>' 'M(anu?)?f(actu)?r?(er)?'             ')$|'
      '(?P<'+PARTNUM     +'>' '(M(anu?)?f(actu)?r?(er)?|P(art)?)'
                              '(#| ?number)'                        ')$|'
      '(?P<'+SUPPLIER    +'>' 'Sup(plier)?|Vendor|Dist(ributor)?'   ')$|'
      '(?P<'+SUPPLIERNUM +'>' '(Sup(plier)?|Vendor|Dist(ributor)?)'
                              '(#| ?number)'                        ')$|'
      '(?P<'+PRICE       +'>' '(Sup(plier)?|Vendor|Dist(ributor)?)?'
                             r'(\$| ?Price)'                        ')$|'
      , flags=re.I)

  META_NAMES = re.compile(
      '(?P<'+SCHFILE+'>' 'source:' ')$|'
      , flags=re.I)

  getAllReferences_re = re.compile(
      " *(([a-z]*)(\d+)|([^-,;]*)) *([-,;]|\.\.|$)"
      , flags=re.I )

  def __init__(self):
    bom.__init__(self)
    # To recognize a row as bom header of is have one of following columns
    self.header_min = [
        {REFERENCE, VALUE    }, 
        {REFERENCE, FOOTPRINT},
        {REFERENCE, DATASHEET},
                      ]

    self.header_excluded = re.compile(
        '('+ITEM    +')$|'
        '('+QUANTITY+')$|'
        , flags=re.I)

    self.meta = {} # A meta key with array of values
    self.refs = {} # A reference key with dict of key and values
    self.lineCnt = 0

  def read(self, filename):
    self.lineCnt = 0
    with open(filename) as bom_file:
      first_file = bom_file.readline()
      for skip_bom, c in enumerate(first_file):
          if ord(c)<=127:
              break

    with open(filename) as bom_file:
      bom_file.read(skip_bom)
      csv_reader = csv.reader(bom_file
          , lineterminator='\n'
          , delimiter=','
          , quotechar='\"'
          , quoting=csv.QUOTE_MINIMAL )

      header = self._findHeader(csv_reader)
      self.header = self._excludedHeader(header)
      self.refs = self._readAllRefs(csv_reader, self.header)

  def _findHeader(self, reader):
    for row in reader:
      self.lineCnt = self.lineCnt+1
      header = {}
      for colIdx, cel in enumerate(row):
        cel = cel.strip()
        m = self.HEADER_NAMES.match(cel)
        if m.lastgroup:
          header[m.lastgroup] = (colIdx, cel, True)
        elif cel:
          header.setdefault(cel, (colIdx, cel, False))

      for hMin in self.header_min:
        if hMin.issubset(header.keys()):
          log.debug("CSV LINE %-3d : %s", self.lineCnt, ', '.join(row))
          return header

      for colIdx, cel in enumerate(row):
        m = self.META_NAMES.match(cel)
        if m.lastgroup:
          self.meta[m.lastgroup] = row[colIdx+1:]
          log.debug("CSV LINE %-3d : %s", self.lineCnt, ', '.join(row))
          break

  def _excludedHeader(self, header):
      return {
        k:v for k, v in header.items() 
          if not self.header_excluded.match(k).group(0)
      }

  def _readAllRefs(self, reader, header):
    log.info("CSV LINE %-3d: Read data for %s", self.lineCnt
        , ', '.join(sorted(self.header.keys())))
    refsData = {}
    refsItemIdx = {}
    for row in reader:
      self.lineCnt = self.lineCnt + 1
      data = {}
      allEmpty = True
      for colID, (colIdx, colname, special) in header.items():
        if colIdx>=len(row):
          log.warn("CSV LINE %-3d: Stop reading", self.lineCnt)
          return refsData

        data[colID] = row[colIdx]

        if row[colIdx]:
            allEmpty = False

      if allEmpty:
          data = {}

      if not data:
        log.warn("Reach end of BOM table at line %d", self.lineCnt)
        return refsData

      if not data[REFERENCE]:
        log.warn("Ignoring line %d - No reference found", self.lineCnt)
        continue

      refs = self.getAllReferences(data[REFERENCE])

      for ref in refs:
        if ref in refsData:
          log.warn("Ignoring %s at line %d - already exist at line(s): %d",
              ref, self.lineCnt, ','.join(refsItemIdx[ref])) 
          continue
        refsData.setdefault(ref, data)
        refsItemIdx.get(ref, []).append(str(self.lineCnt))

    return refsData


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
