#!/bin/python
"""
    @package
    Update eeschema symbol files from CSV BOM list.
"""
import sys
import os
import logging
from Queue import Queue

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

from libs import utils
from libs import eeschematic
from libs import bom


log = logging.getLogger(__name__)


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
  myBom = bom.csv_bom()
  myBom.read(bom_filename)
  bomHeaderTexts = myBom.getHeaderTexts()
  if not sch_filename:
    sch_filename = myBom.getSchFileName()
  
  sch_filename = utils.normPath(sch_filename, os.path.dirname(bom_filename))

  # Create a component field name map to ColID
  fieldNameToColID = myBom.genColNameToHeaderID()
  fieldNameToColID.update(
    {
      eeschematic.FIELD_REF_NAME : None      ,
      eeschematic.FIELD_VAL_NAME : bom.VALUE     ,
      eeschematic.FIELD_FP_NAME  : bom.FOOTPRINT ,
      eeschematic.FIELD_PDF_NAME : bom.DATASHEET ,
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
        maxFieldNum = 0
        updatedFields = {}
        fields = e.info[eeschematic.COMP_FIELDS]
        for fieldNum, fieldInfo in fields.items():
          #log.debug("%s - %s", fieldNum, {k:str(v) for k, v in fieldInfo.items()})
          bomColID = str(fieldInfo[eeschematic.FIELD_NAME])
          bomColID = fieldNameToColID.get(bomColID, bomColID)
          newValue = fieldsValue.get(bomColID)
          if newValue is not None:
            newValue = newValue.strip()
            fieldInfo[eeschematic.FIELD_VALUE].setAndQuoteValue(newValue)

          _num = int(fieldNum)
          if _num > maxFieldNum:
            maxFieldNum = _num

          updatedFields[bomColID] = fieldInfo

        # Insert Populate field if is has value and not exist in the
        # schematic yet
        val_field = updatedFields.get(bom.VALUE, {})
        pop_val = fieldsValue.get(bom.POPULATE)
        if pop_val and (bom.POPULATE not in updatedFields):
          pop_field = e.duplicate(val_field
              , fields[str(maxFieldNum)][eeschematic.FIELD_VALUE])
          maxFieldNum = maxFieldNum + 1
          pop_field[eeschematic.FIELD_NUMBER].setValue(str(maxFieldNum))
          pop_field[eeschematic.FIELD_VALUE].setAndQuoteValue(pop_val)
          pop_field[eeschematic.FIELD_NAME].setAndQuoteValue(
            bomHeaderTexts[bom.POPULATE])
        else:
          pop_field = updatedFields.get(bom.POPULATE, {})

        # + Hide Value if the Populate field has value, and it locate at
        # same position as Value
        # + Unhide Value if the Populate field has no value, and its
        # location at same position as Value
        valX = int(str(val_field.get(eeschematic.FIELD_POSX,'0')))
        valY = int(str(val_field.get(eeschematic.FIELD_POSY,'0')))
        popX = int(str(pop_field.get(eeschematic.FIELD_POSX,'1')))
        popY = int(str(pop_field.get(eeschematic.FIELD_POSY,'1')))
        if valX==popX and valY==popY:
          if pop_val=="DNP":
            # Show pop, Hide value
            val_field[eeschematic.FIELD_FLAGS].setValue("0001")
            pop_field[eeschematic.FIELD_FLAGS].setValue("0000")
          else:
            val_field[eeschematic.FIELD_FLAGS].setValue("0000")
            pop_field[eeschematic.FIELD_FLAGS].setValue("0001")
            if not pop_val:
                log.info("Remove %s %s field", effRefs, pop_field[eeschematic.FIELD_NAME])
                e.delete(pop_field)

        # Update Symbol value
        newValue = fieldsValue.get(bom.SYMBOL, None)
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
      format='%(asctime)s [%(filename)s:%(lineno)-4d] %(levelname)7s - %(message)s')
  main_cli()
  tests()
