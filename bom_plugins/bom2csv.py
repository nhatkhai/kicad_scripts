#!/bin/python
"""
    @package
    Generate a csv BOM list.
    Components are sorted by ref and grouped by Value, Manufacturer,
    Partnumber, Footprint, Datasheet

    Item, Qty, Reference(s), Value, LibPart, Footprint, Datasheet
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
import kicad_netlist_reader


def myEqu(self, other):
    """myEqu is a more advanced equivalence function for components which is
    used by component grouping. Normal operation is to group components based
    on their value and footprint.

    In this example of a custom equivalency operator we compare the
    value, the part name and the footprint.

    """
    result = True
    if self.getValue() != other.getValue():
        result = False
    elif self.getField('Manufacturer') != other.getField('Manufacturer'):
        result = False
    elif self.getField('PartNumber') != other.getField('PartNumber'):
        result = False
    elif self.getFootprint() != other.getFootprint():
        result = False
    elif self.getDatasheet() != other.getDatasheet():
        result = False
    #elif self.getPartName() != other.getPartName():
    #    result = False

    return result


def main():
  # Override the component equivalence operator - it is important to do this
  # before loading the netlist, otherwise all components will have the original
  # equivalency operator.
  kicad_netlist_reader.comp.__eq__ = myEqu
  
  if len(sys.argv) != 3:
      print("Usage ", sys.argv[0], "<generic_netlist.xml> <output.csv>", file=sys.stderr)
      sys.exit(1)
  
  # Generate an instance of a generic netlist, and load the netlist tree from
  # the command line option. If the file doesn't exist, execution will stop
  net = kicad_netlist_reader.netlist(sys.argv[1])
  
  # Open a file to write to, if the file cannot be opened output to stdout
  # instead
  try:
      sys.argv[2] = sys.argv[2]+".csv"
      f = open(sys.argv[2], 'w')
  except IOError:
      e = "Can't open output file for writing: " + sys.argv[2]
      print( sys.argv[0], ":", e, sys.stderr )
      f = sys.stdout
  
  # subset the components to those wanted in the BOM, controlled
  # by <configure> block in kicad_netlist_reader.py
  components = net.getInterestingComponents()
  
  compfields = net.gatherComponentFieldUnion(components)
  partfields = net.gatherLibPartFieldUnion()

  columnset = compfields | partfields \
            | {'Supplier', 'Supplier Number', 'Supplier Price'}  # union
  
  # remove Reference, Value, Datasheet, and Footprint, they will come from 'columns' below
  columnset -= { 'Reference', 'Value',
                 'Datasheet', 'Footprint',
                 'Manufacturer','PartNumber',
                 'Supplier', 'Supplier Number', 'Supplier Price' }
  
  # prepend an initial 'hard coded' list and put the enchillada into list 'columns'
  columns = ['Item', 'Qty',
             'Reference(s)', 'Value',
             'Manufacturer','PartNumber',
             'Supplier', 'Supplier Number', 'Supplier Price'] \
          + sorted(list(columnset)) \
          + ['LibPart', 'Footprint', 'Datasheet'] \
  
  # Create a new csv writer object to use as the output formatter
  out = csv.writer( f, lineterminator='\n', delimiter=',', quotechar='\"', quoting=csv.QUOTE_MINIMAL )
  
  # override csv.writer's writerow() to support encoding conversion (initial encoding is utf8):
  def writerow(acsvwriter, iColumns):
      utf8row = []
      for col in iColumns:
          utf8row.append( str(col) )  # currently, no change
      acsvwriter.writerow( utf8row )
  
  # Output a set of rows as a header providing general information
  # No that, add the UTF-8-BOM to allow Excel read this file a UTF-8
  writerow( out, ['\xef\xbb\xbfSource:', net.getSource()] )
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
      del row[:]
      row.append('')                                      # item is blank in individual table
      row.append('')                                      # Qty is always 1, why print it
      row.append( c.getRef() )                            # Reference
      row.append( c.getValue() )                          # Value
  
      # from column 4 upwards, use the fieldnames to grab the data
      for field in columns[4:]:
          row.append( c.getField( field ) )
  
      writerow( out, row )
  
  writerow( out, [] )                        # blank line
  writerow( out, [] )                        # blank line
  writerow( out, [] )                        # blank line
  
  writerow( out, ['Collated Components:'] )
  writerow( out, [] )                        # blank line
  writerow( out, columns )                   # reuse same columns
  
  # Get all of the components in groups of matching parts + values
  # (see kicad_netlist_reader.py)
  grouped = net.groupComponents(components)
  
  # Output component information organized by group, aka as collated:
  item = 0
  for group in grouped:
      del row[:]

      # Add the reference of every component in the group and keep a reference
      # to the component so that the other data can be filled in once per group
      refs = []
      c = None
      for component in group:
          refs.append(component.getRef())
          c = component
      refs = ', '.join(refs)
  
      # Fill in the component groups common data
      item += 1
      row.append( item )
      row.append( len(group) )
      row.append( refs )
      row.append( c.getValue() )
  
      # from column 4 upwards, use the fieldnames to grab the data
      for field in columns[4:]:
          row.append( net.getGroupField(group, field) )
  
      writerow( out, row  )
  
  f.close()
  
  import os
  os.startfile(sys.argv[2])

if __name__ == "__main__":
    main()
