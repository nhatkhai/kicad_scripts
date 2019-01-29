#!/bin/python
"""
    @package
    Generate multiple BOM tables in a csv file from a KiCad XML netlist.
    
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

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

# Import the KiCad python helper module and the csv formatter
from libs import kicad_netlist_reader


def groupIdentity(component):
    """Operation return a data help identify which component group belong to

    In this example of a custom equivalency operator we compare the
    value, Manufacturer, PartNumber, Datasheet, Footprint, and POP
    """
    return tuple(component.getField(n) for n in (  
                'Value'
              , 'Manufacturer', 'PartNumber', 'Datasheet'
              , 'Footprint', 'POP'))


def main():
  if len(sys.argv) != 3:
      print("Usage ", sys.argv[0], "<generic_netlist.xml> <output.csv>", file=sys.stderr)
      sys.exit(1)
  
  # Open a file to write to, if the file cannot be opened output to stdout
  # instead
  try:
      sys.argv[2] = sys.argv[2]+".csv"
      f = open(sys.argv[2], 'w')
  except IOError:
      e = "Can't open output file for writing: " + sys.argv[2]
      print( sys.argv[0], ":", e, sys.stderr )
      f = sys.stdout
  
  # Generate an instance of a generic netlist, and load the netlist tree from
  # the command line option. If the file doesn't exist, execution will stop
  net = kicad_netlist_reader.netlist(sys.argv[1])
  
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
  
  # remove Reference, Value, Datasheet, and Footprint, they will come from 'columns' below
  columnset -= set(specialColOrder)
  columnset -= set(specialSuppCol)
  columnset -= {'Reference'}
  columnset -= set(specialPosfixCol)
  
  # prepend an initial 'hard coded' list and put the enchillada into list 'columns'
  columns = specialPrefixCol \
          + specialColOrder \
          + specialSuppCol \
          + sorted(list(columnset)) \
          + specialPosfixCol 
  
  # Create a new csv writer object to use as the output formatter
  out = csv.writer( f, lineterminator='\n', delimiter=',', quotechar='\"', quoting=csv.QUOTE_MINIMAL )
  
  # override csv.writer's writerow() to support encoding conversion (initial encoding is utf8):
  def writerow(acsvwriter, iColumns):
      utf8row = []
      for col in iColumns:
          utf8row.append( str(col) )  # currently, no change
      acsvwriter.writerow( utf8row )
  
  # Output a set of rows as a header providing general information
  # No that, add the UTF-8-BOM to allow Excel read this file as UTF-8
  # However, when save from Excel, it will not work with UTF-8-BOM. So for
  # saving back we better to not insert UTF-8-BOM code
  #writerow( out, ['\xef\xbb\xbfSource:', net.getSource()] )
  writerow( out, ['Source:', net.getSource()] )
  writerow( out, ['Date:', net.getDate()] )
  writerow( out, ['Tool:', net.getTool()] )
  writerow( out, ['Generator:', sys.argv[0]] )
  writerow( out, ['Component Count:', len(components)] )
  writerow( out, [] )
  writerow( out, ['Individual Components:'] )
  writerow( out, [] )                        # blank line
  writerow( out, columns )
  
  # Output all the interesting components individually first:
  row = []
  for c in components:
      row = [c.getField( field ) for field in columns]
      writerow( out, row )
  
  writerow( out, [] )                        # blank line
  writerow( out, [] )                        # blank line
  writerow( out, [] )                        # blank line
  
  writerow( out, ['Grouped Style:'] )
  writerow( out, [] )                        # blank line
  writerow( out, columns )                   # reuse same columns
  
  # Get all of the components in groups of matching parts + values
  # (see kicad_netlist_reader.py)
  grouped = net.groupComponents(groupIdentity, components)
  
  # Output component information organized by group, aka as collated:
  item = 0
  for group in grouped:
      item += 1
      row = [item, len(group)]
  
      for field in columns[2:]:
          row.append( net.getGroupField(group, field) )
  
      writerow( out, row  )
  
  f.close()
  
  import os
  os.startfile(sys.argv[2])

if __name__ == "__main__":
    main()
