#!/bin/python
"""
Update eeschema symbol fields from specified CSV BOM file.
"""
import sys
import os
import logging
import argparse
from Queue import Queue

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

from libs import utils
from libs import eeschematic
from libs import bom


log = logging.getLogger(__name__)


def main_cli(argv=None):
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument('bom', type=str, metavar='bom.csv')
  p.add_argument('sch', type=str, metavar='root_schematic_file.sch', nargs='?'
      , help = '''can be automatically extracted from csv file where
          "Source:" field specified in the header meta data. This usually
          create by eeschema BOM generator scripts''')
  p = p.parse_args(argv)

  bom_filename = p.bom
  sch_filename = p.sch

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

  # Go parse through all relevant schematic file for update component
  # fields
  log.debug("Update component values")
  with eeschematic.schCompIter(sch_filename
          , lambda f: iter(eeschematic.schMapper(f, f+'.new'))) as sch:
    for e, effRefs in sch:
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
    sheetARs = sch.getSubSheetARs()
    # Now rename current schematic files for backup
    for schfile in sheetARs.keys():
        bakSchFile = schfile + '.bak'
        log.info("  %s", bakSchFile)
        os.rename(schfile, bakSchFile)

    # Now rename new schematic files
    for schfile in sheetARs.keys():
        os.rename(schfile + '.new', schfile)


#
# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  import doctest
  import os
  import time

  doctest.testmod(verbose=False)

  log.info("Test sch1 for normal use case")
  main_cli(['test_files/sch1/sch1.csv'])

  for f in ('sch1.sch', 'a1.sch'):
    actual = os.system(' '.join(('diff -s -q --strip-trailing-cr'
      , 'test_files/sch1/%s' % f
      , 'test_files/sch1/%s.bak' % f
    ,)))
    assert actual==0, "diff[%d] - generated %s not match" % (actual, f)

  sys.exit(0)


if __name__ == "__main__":
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s [%(filename)s:%(lineno)-4d] %(levelname)7s - %(message)s')

  if '--test' in sys.argv: 
    tests()

  main_cli()
