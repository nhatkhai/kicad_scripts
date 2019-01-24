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
    self.meta = {} # A meta key with array of values
    self.header={} # A PROGRAM_HEADER_ID -> (COLUMN_INDEX, COLUMN_NAME, FALSE_IF_UNKNOWN_USER_COLUMN)
    self.refs = {} # A reference key with dict of field to values

  def getSchFileName(self):
    raise NotImplemented("Base class method")

  def getReferences(self):
    return self.refs

  def transformToSch(self, references):
    """Combine supplier, price, and part number into once supplier field
    """
    for ref in references:
      values = self.refs.get(ref, {})
      values[SUPPLIER] = ":".join([a 
        for a in (values.pop(k, None) for k in (SUPPLIER, SUPPLIERNUM, PRICE))
        if a is not None])
      if values.get(VALUE, '').upper() in {'DO NOT POPULATE'}:
        values[VALUE] = "DNP"


  def joinValues4Refs(self, references):
    """
    @param references: a collection of references
    """
    values = [self.refs.get(ref,{}) for ref in references]
    values, isjoined = bom._join2Dict(values)
    for ref in references: 
      self.refs[ref] = values
    return values, isjoined

  def genSchFieldNameToBomColID(self):
    return {fieldName:colID 
        for colID, (colIdx, fieldName, special) in self.header.items()}

  @staticmethod
  def _join2Dict(dicts, sep="; "):
    keys = set()
    for d in dicts: keys.update(d.keys())

    new = {}
    isjoined = False
    for key in keys:
      val = set()
      for d in dicts:
        val.add(d.get(key,''))
      if len(val)>1:
        isjoined = True
      new[key] = sep.join(val)

    return new, isjoined


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
      " *(([a-z]*)(\d+)|([^,;]*)) *([-,;]?)"
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

  def getSchFileName(self):
    return self.meta.get(SCHFILE, [None])[0]

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
      self.header = {k:v for k, v in header.items() 
          if not self.header_excluded.match(k).group(0)}
      log.info("Obtain info for %s", sorted(self.header.keys()))
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
          log.debug("CSV LINE %-3d : %s", self.lineCnt, row)
          return header

      for colIdx, cel in enumerate(row):
        m = self.META_NAMES.match(cel)
        if m.lastgroup:
          self.meta[m.lastgroup] = row[colIdx+1:]
          log.debug("CSV LINE %-3d : %s", self.lineCnt, row)
          break

  def _readAllRefs(self, reader, header):
    log.debug("%s", header.keys())
    refsData = {}
    refsItemIdx = {}
    for row in reader:
      self.lineCnt = self.lineCnt + 1
      data = {}
      for colID, (colIdx, colname, special) in header.items():
        if colIdx>=len(row):
          log.warn("Stop reading at line %d", self.lineCnt)
          return refsData

        if row[colIdx]:
          data[colID] = row[colIdx]

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

  @staticmethod
  def getAllReferences(refs):
    """ Return array of reference split out from the refs string

    @example: 
    >>> csv_bom.getAllReferences('C1-C4  ,  C21; C23')
    ['C1', 'C2', 'C3', 'C4', 'C21', 'C23']
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
        if state == "-":
          for i in range(refNum, nextRefNum):
            allref.append(m.group(2) + str(i)) 
        else:
          allref.append(m.group(1)) 

        refNum = nextRefNum
        state  = m.group(5)

    return allref


def main_cli():
  if len(sys.argv)<2:
    log.info("""
    %s csv_file.csv [root_schematic_file.sch]

    root_schematic_file.sch can be automatically extracted from csv file
    where "Source:" field specified in the header meta data. This usually
    create by eeschema BOM generator scripts
    """, os.path.basename(sys.argv[0]))
    sys.exit(1)

  bom_filename = sys.argv[1] if len(sys.argv)>1 else None
  sch_filename = sys.argv[2] if len(sys.argv)>2 else None
  if bom_filename == "--test": return

  log.info("Reading %s", bom_filename)

  # Read all BOM data into memory
  myBom = csv_bom()
  myBom.read(bom_filename)
  if not sch_filename:
    sch_filename = myBom.getSchFileName()
  
  # Normalize path that can be either from Windows/Linux style
  # By first check if any "/" character in the path
  test_path = sch_filename.split("/")

  if len(test_path)==0:
  # Look like is it windows path, so we split it in Window way
    test_path = sch_filename.split("\\")

  # Check first part of this path to see if it is a relative path
  if test_path[0] in ("..", ".", ""):
    bom_path = os.path.dirname(bom_filename)
    sch_filename = os.path.normpath(os.path.join(bom_path, sch_filename))
  else:
    sch_filename = os.path.sep.join(test_path)

  # Create a component field name map to ColID
  fieldNameToColID = myBom.genSchFieldNameToBomColID()
  fieldNameToColID.update(
    {
      eeschematic.FIELD_REF_NAME : None      ,
      eeschematic.FIELD_VAL_NAME : VALUE     ,
      eeschematic.FIELD_FP_NAME  : FOOTPRINT ,
      eeschematic.FIELD_PDF_NAME : DATASHEET ,
    }
  )

  log.info("Master schematic file is %s", sch_filename)

  # Travel through all schematic file tree to figure out what is the set of
  # relevant AR ID need to be looking for
  log.debug("Obtaining schematic hierarchy structure")
  #
  # Graph if all sheet link with its AR ID
  # schfilename -> [('AR_ID', 'subschfilename')]
  sheetTree = {}

  sheets = Queue()
  sheets.put( (sch_filename, sheetTree.setdefault(sch_filename, []),) )
  while not sheets.empty():
    schfile, schLinks = sheets.get()
    log.debug("  Visiting %s", schfile)

    rootPath = os.path.dirname(schfile)

    with open(schfile,'r') as f:
      for e, state in eeschematic.schIter(f):
        #log.debug("%s %10s ** %s", len(e._processor), state, e.line[:-1])
        if state!=e.SUB_SCH_EX: 
          continue

        subAR = str(e.info[eeschematic.SHEET_ID])
        subSchFile = os.path.join(rootPath, str(e.info[eeschematic.SHEET_FILE]))

        schLinks.append( (subAR, subSchFile,) )

        if subSchFile not in sheetTree:
          sheets.put( (subSchFile, sheetTree.setdefault(subSchFile, []),) )

  # Walk through the sch graph to generate a set of AR path that relevant
  # to the root schematic only
  log.debug("Calculate all relevant AR path")
  sheetARs = { sch_filename : set() }
  sheets = Queue()
  sheets.put( (sch_filename, '',) )
  while not sheets.empty():
    schfile, curAR = sheets.get()
    log.debug("  Visiting %s", schfile)
    for subAR, subSchFile in sheetTree[schfile]:
      subAR = curAR + '/' + subAR 
      sheetARs.setdefault(subSchFile, set()).add(subAR)
      sheets.put( (subSchFile, subAR) )
  del sheetTree

  # Go parse through all relevant schematic file for update component
  # fields
  log.debug("Update component values")
  for schfile, arPaths in sheetARs.items():
    log.info("  Processing %s", schfile)
    with open(schfile, 'r') as f, \
         open(schfile+".new", 'w') as of:
      for e, state in eeschematic.schMapper(f, of):
        if state != e.COMP_EX:
          continue
       
        # Find a set of relevant references for this components
        comARs = e.info.get(eeschematic.COMP_AR)
        effRefs = set()
        if comARs is None or len(arPaths)==0:
          ref = str(e.info[eeschematic.COMP_REF])
          effRefs.add(ref)
        else:
          comID = "/" + str(e.info[eeschematic.COMP_ID])
          for comARPath, values in comARs.items():
            if comARPath[0]=='"': comARPath=comARPath[1:-1]
            if comARPath.endswith(comID):
              if comARPath[0:-len(comID)] in arPaths:
                ref = str(values[eeschematic.COMP_REF])
                if ref[0]=='"': ref=ref[1:-1]
                effRefs.add(ref)

        if len(arPaths)!=len(effRefs):
          log.error("Line %d - Cannot find all %d AR Path" 
              % (e.lineCnt, len(arPaths)) )
        #log.debug("%s - %s", os.path.basename(schfile), effRefs)

        myBom.transformToSch(effRefs)

        # Now look into BOM data for update fields
        fieldsValue, isjoined = myBom.joinValues4Refs(effRefs)
        if not fieldsValue:
          continue

        if isjoined:
          log.warn("%s fields values had been combined", ','.join(effRefs) )

        # Update field values
        for fieldNum, fieldInfo in e.info[eeschematic.COMP_FIELDS].items():
          #log.debug("%s - %s", fieldNum, {k:str(v) for k, v in fieldInfo.items()})
          bomColID = str(fieldInfo[eeschematic.FIELD_NAME])
          bomColID = fieldNameToColID.get(bomColID, bomColID)
          newValue = fieldsValue.get(bomColID)
          if newValue is not None:
            newValue = newValue.strip()
            fieldInfo[eeschematic.FIELD_VALUE].setAndQuoteValue(newValue)

        # TODO: Insert Populate field if is has value
        # Hide Value if the Populate field has value, and it locate at same 
        # position as Value
        # Unhide Value if the Populate field has no value, and its location
        # at same position as Value

        # Update Symbol value
        newValue = fieldsValue.get(SYMBOL, None)
        if newValue is not None:
          newValue = newValue.strip()
          comLib = e.info[eeschematic.COMP_LIB]

          # Check current symbol style
          if newValue[:1] == ':': newValue = newValue[1:]
          i = newValue.find(':') + 1

          # Remove lib name if current did not use the 5.x style, or
          # lib name is empty in newValue
          if i==1 or (':' not in comLib.getValue()):
              newValue = newValue[i:]
          e.info[eeschematic.COMP_LIB].setValue(newValue)


  log.info("Backup old schematic files:")
  # Now rename current schematic files for backup
  for schfile in sheetARs.keys():
    bakSchFile = schfile + '.bak'
    log.info("  %s", bakSchFile)
    os.rename(schfile, bakSchFile)

  # Now rename new schematic files
  for schfile in sheetARs.keys():
    os.rename(schfile + '.new', schfile)

  sys.exit(0)

#
# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s [%(filename)s:%(lineno)-4d] %(message)s')
  main_cli()
  tests()
