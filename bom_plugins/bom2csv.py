#!/bin/python
"""
@package Generate multiple BOM tables in a csv file from a KiCad XML netlist.

* A BOM table with individual reference
* A BOM table with grouped by ref and grouped by Value, Manufacturer,
    PartNumber, Datasheet, Footprint, and POP/Population. Other fields
    will be combine with comma separators.

All BOM tables would contains following columns if existed:
    Item, Qty, POP, 
    Reference(s), Value, 
    Manufacturer, PartNumber,
    Supplier, Supplier Number, Supplier Price, 
    Description, 
    ... <-- customized/unrecognized fields
    LibPart, Footprint, 
    Datasheet

The Supplier, Supplier Number, Supplier Price are breaking out from a
field call "Supplier" with following format:
    SUPPLIER_NAME:SUPPLIER_NUMBER:$SUPPLIER_PRICE

NOTE: Inserting UTF-8-BOM into csv will make excel show UTF-8
    characters correctly. But Excel incorrectly saves back modified csv
    file. This script will not insert UTF-8-BOM for this purpose.
"""

from __future__ import print_function
import csv
import sys
import os
import logging
import argparse

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

# Import the KiCad python helper module and the csv formatter
from libs import kicad_netlist_reader
from libs import utils


log = logging.getLogger(__name__)


def groupIdentity(component):
    """Operation return a data help identify which component group belong to

    In this example of a custom equivalency operator we compare the
    value, Manufacturer, PartNumber, Datasheet, Footprint, and POP
    """
    return tuple(component.getField(n) for n in (  
                'Value'
              , 'Manufacturer', 'PartNumber', 'Datasheet'
              , 'Footprint', 'POP'))


def main_cli(argv=None):
  p = argparse.ArgumentParser(description=__doc__,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument('xml', type=str, metavar='GENERIC_NETLIST.XML'
      , help = "eeschema intermediate netlist file")
  p.add_argument('bom', type=str, metavar='OUTPUT_BOM', nargs='?'
      , help = "Specify csv filename")
  p.add_argument('--utf8' , action='store_const', const=True
      , help = "Insert UTF-8-BOM code into csv file")
  p.add_argument('-g', '--group'
      , dest='bomtype', action='append_const', const='g'
      , help = "Generate grouped BOM table")
  p.add_argument('-i', '--individual'
      , dest='bomtype', action='append_const', const='i'
      , help = "Generate BOM table for each reference individually")
  p.add_argument('--noopen', action='store_const', const=True
      , help= "Disable auto open the BOM file after generated")
  p = p.parse_args(argv)

  if not p.bom:
    p.bom = os.path.splitext(p.xml)[0]

  if not p.bom.endswith('.csv'):
    p.bom = p.bom + '.csv'

  if p.bomtype is None:
    p.bomtype = {'g', 'i'}
  else:
    p.bomtype = set(p.bomtype)

  # Open a file to write to, if the file cannot be opened output to stdout
  # instead
  try:
      f = open(p.bom, 'w')
  except IOError:
      e = "Can't open output file for writing: " + p.bom
      print( sys.argv[0], ":", e, sys.stderr )
      f = sys.stdout
  
  # Generate an instance of a generic netlist, and load the netlist tree from
  # the command line option. If the file doesn't exist, execution will stop
  net = kicad_netlist_reader.netlist(p.xml)
  
  # subset the components to those wanted in the BOM, controlled
  # by <configure> block in kicad_netlist_reader.py
  components = net.getInterestingComponents()
  
  compfields = net.gatherComponentFieldUnion(components)
  partfields = net.gatherLibPartFieldUnion()

  specialPrefixCol= ['Item', 'Qty',]

  specialColOrder = []
  if 'POP' in compfields:
    specialColOrder.append('POP')
  specialColOrder.extend(['Reference(s)', 'Value', 'Manufacturer','PartNumber',])

  if 'Supplier' in compfields:
    specialSuppCol  = ['Supplier', 'Supplier Number', 'Supplier Price',]

  specialPosfixCol= ['LibPart', 'Footprint', 'Datasheet']

  columnset = compfields | partfields | set(specialSuppCol)  # union
  
  # Remove always included columns
  columnset -= set(specialColOrder)
  columnset -= set(specialSuppCol)
  columnset -= {'Reference'}
  columnset -= set(specialPosfixCol)
  
  # Create a complete set of columns to generate BOM table
  columns = specialPrefixCol \
          + specialColOrder \
          + specialSuppCol \
          + sorted(list(columnset)) \
          + specialPosfixCol 
  
  # Create a new csv writer object to use as the output formatter
  out = csv.writer( f
      , lineterminator='\n'
      , delimiter=','
      , quotechar='\"'
      , quoting=csv.QUOTE_MINIMAL )
  
  # override csv.writer's writerow() to support encoding conversion
  # (initial encoding is utf8):
  def writerow(acsvwriter, iColumns):
      acsvwriter.writerow( [str(c) for c in iColumns] )
  
  if p.utf8:
    source = ['\xef\xbb\xbfSource:']
  else:
    source = [            'Source:']
  source.append( utils.relPath( net.getSource(), os.path.dirname(p.bom) ) )

  # Output a set of rows as a header providing general information
  writerow( out, source )
  writerow( out, ['Date:', net.getDate()] )
  writerow( out, ['Tool:', net.getTool()] )
  writerow( out, ['Generator:', sys.argv[0]] )
  writerow( out, ['Component Count:', len(components)] )
  writerow( out, [] )
  
  if 'i' in p.bomtype:
  # Output all the interesting components individually first:
    writerow( out, ['Individual Components:'] )
    writerow( out, [] )                        # blank line
    writerow( out, columns )
    row = []
    for c in components:
        row = [c.getField( field ) for field in columns]
        writerow( out, row )
    
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line
  
  if 'g' in p.bomtype:
    writerow( out, ['Grouped Style:'] )
    writerow( out, [] )                        # blank line
    writerow( out, columns )                   # reuse same columns
  
    # Get all of the components in groups 
    grouped = net.groupComponents(groupIdentity, components)
    
    # Output component information organized by group, aka as collated:
    for item, group in enumerate(grouped):
        row = [item+1, len(group)]
    
        for field in columns[2:]:
            row.append( net.getGroupField(group, field) )
    
        writerow( out, row  )
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line

  f.close()
  if not p.noopen:
    try: 
      os.startfile(p.bom)
    except:
      pass


#
# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  import os
  import doctest

  doctest.testmod(verbose=False)

  log.info("Test sch1 for normal use case")
  main_cli(['--noopen'
    , 'test_files/sch1/sch1.xml'
    , 'test_files/sch1/test_bom2csv.csv'
  ])

  actual = os.system(' '.join(('diff -s --strip-trailing-cr'
  , 'test_files/sch1/sch1.csv' 
  , 'test_files/sch1/test_bom2csv.csv'
  ,)))
  assert actual==0, "diff[%d] - generated test_bom2csv.csv not match" % actual

  sys.exit(0)


if __name__ == "__main__":
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s [%(filename)s:%(lineno)-4d] %(levelname)7s - %(message)s')

  if '--test' in sys.argv: 
    tests()

  main_cli()
