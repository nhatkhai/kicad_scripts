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

import csv
import sys
import os
import re
import logging
import argparse

lib_path = os.path.join(os.path.dirname(sys.argv[0]),'..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

# Import the KiCad python helper module and the csv formatter
from libs import kicad_netlist_reader
from libs import utils
from libs import eeschematic
from libs import bom


log = logging.getLogger(__name__)


def groupIdentity(component):
    """Operation return a data help identify which component group belong to

    In this example of a custom equivalency operator we compare the
    value, Manufacturer, PartNumber, Datasheet, Footprint, and POP
    """
    return tuple(component.get(n) for n in (  
                bom.VALUE
              , bom.MANUFACTURER, bom.PARTNUM, bom.DATASHEET
              , bom.FOOTPRINT, bom.POPULATE))


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
  
  infileext = os.path.splitext(p.xml)[1]
  myBom = { 
    '.xml' : xml_bom,
    '.sch' : sch_bom,
    '.csv' : bom.csv_bom,
  }.get(infileext.lower(), notsupportedfile)(p.xml)

  exclude_filters = {
      bom.REFERENCE : re.compile("#.*"),
  }

  myBom.read(exclude_filters)

  meta = myBom.getMetaData()
  bomHeader = myBom.getHeaderTexts()
  refs = myBom.getReferences()

  for data in refs.itervalues():
    supplier = data.get(bom.SUPPLIER)
    if supplier is not None:
      suppInfo = supplier.split(":")
      if len(supplier)>0: data[bom.SUPPLIER]   = suppInfo[0]
      if len(supplier)>1: data.setdefault(bom.SUPPLIERNUM, suppInfo[1])
      if len(suppInfo)>2: data.setdefault(bom.PRICE      , suppInfo[2])

  specialPrefixCol= [bom.ITEM, bom.QUANTITY,]

  specialColOrder = []
  if bom.POPULATE in bomHeader:
    specialColOrder.append(bom.POPULATE)
  specialColOrder.extend([bom.REFERENCE, bom.VALUE, bom.MANUFACTURER, bom.PARTNUM])

  specialSuppCol  = []
  if bom.SUPPLIER in bomHeader:
    specialSuppCol  = [bom.SUPPLIER, bom.SUPPLIERNUM, bom.PRICE,]

  specialPosfixCol= [bom.SYMBOL, bom.FOOTPRINT, bom.DATASHEET]

  colIDset = set(bomHeader.keys())

  # Remove always included colIDs
  colIDset -= set(specialColOrder)
  colIDset -= set(specialSuppCol)
  colIDset -= {'Reference'}
  colIDset -= set(specialPosfixCol)
  
  # Create a complete set of colIDs to generate BOM table
  colIDs = specialPrefixCol \
        + specialColOrder \
        + specialSuppCol \
        + sorted(list(colIDset)) \
        + specialPosfixCol 

  # Overwrite some of user header text
  myText = {
      bom.ITEM        : 'Item',
      bom.QUANTITY    : 'Qty',
      bom.POPULATE    : 'POP',
      bom.REFERENCE   : 'Reference(s)',
      bom.SUPPLIERNUM : 'Supplier Number',
      bom.PRICE       : 'Supplier Price',
      bom.SYMBOL      : 'LibPart',
  }
  for colID, colText in myText.iteritems():
    if colID in bomHeader or colID in colIDs:
      bomHeader[colID] = colText
  
  # Obtain user header text
  columns = [bomHeader.get(c, c) for c in colIDs]

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
  source.append( utils.relPath( meta.get(bom.SCHFILE)[0]
    , os.path.dirname(p.bom) ) )

  # Output a set of rows as a header providing general information
  writerow( out, source )
  for a in ['Date', 'Tool']:
    if a in meta:
      writerow( out, [a + ':', meta.get(a)[0]] )
  writerow( out, ['Generator:', sys.argv[0]] )
  writerow( out, ['Component Count:', len(refs)] )
  writerow( out, [] )
  
  # TODO - I'm here
  r = re.compile('[0-9]+(\.[0-9]+)?')
  
  if 'i' in p.bomtype:
  # Output all the interesting references individually first:
    writerow( out, ['Individual Components:'] )
    writerow( out, [] )                        # blank line
    writerow( out, columns )
    row = []

    sortedRefs = sorted(refs.iterkeys()
      , key=lambda g: r.sub( lambda m: '%016.8f' % float(m.group(0)), g )
    )

    for ref in sortedRefs:
      data = refs[ref]
      row = [data.get( field, '' ) for field in colIDs]
      writerow( out, row )
    
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line
    writerow( out, [] )                        # blank line
  
  if 'g' in p.bomtype:
    writerow( out, ['Grouped Style:'] )
    writerow( out, [] )                        # blank line
    writerow( out, columns )                   # reuse same columns
  
    # Group all references that have the same set of info
    groups = {}
    for ref, data in refs.iteritems():
        groups.setdefault(groupIdentity(data), []).append(ref)

    # Each group is a list of components, we need to sort each list first
    # to get them in order as this makes for easier to read BOM's
    for g in groups.itervalues():
        g.sort(key=lambda gg: r.sub(
            lambda m: '%016.8f' % float(m.group(0)), gg))

    # Finally, sort the groups to order the references alphabetically
    groups = sorted(groups.itervalues()
              , key=lambda gg: r.sub(
                lambda m: '%016.8f' % float(m.group(0)), gg[0]))
    #TODO - HERE

    # Output component information organized by group, aka as collated:
    for item, group in enumerate(groups):
        row = [item+1, len(group)]
    
        for field in colIDs[2:]:
          vals = set(refs[ref].get(field, '') for ref in group)
          vals-= {''}
          vals = sorted(vals, 
              key=lambda v: r.sub(
                lambda m: '%016.8f' % float(m.group(0)), v))
          row.append( ', '.join(vals) )
    
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

def notsupportedfile(filename):
  log.error("%s is not a supported file type", filename)
  exit(1)


class xml_bom(bom.bom):
  HEADER_NAMES = re.compile(')$|'.join(bom.bom.BOM_HEADER_ID_REGEXS + [''])
      , flags=re.I)

  def __init__(self, filename):
    bom.bom.__init__(self)
    self.meta[bom.SRCFILE] = [filename]

  def read(self, exclude_filters=None):
    if exclude_filters is None:
      exclude_filters = {}

    filename = self.getSrcFileName()

    # Load xml netlist file ( Generic Netlist file )
    net = kicad_netlist_reader.netlist(filename)

    # Save meta data in to meta dict
    self.meta[bom.SCHFILE] = [net.getSource()]
    self.meta['Date']      = [net.getDate()  ]
    self.meta['Tool']      = [net.getTool()  ]
    
    # Collect a map of lib name to libparts class for latter retrieval for
    # component fields names
    libByNames = {}
    for lib in net.getLibparts():
      libByNames[lib.getLibName()] = lib 

    for c in net.getComponents():
      ref     = c.getRef()
      cData   = {}
      cHeader = {}

      fields = {'libpart'}
      fields.update(c.getFieldNames())
      lib = libByNames.get( c.getLibName() )
      if lib is not None:
        fields.update( lib.getFieldNames() )

      for f in fields:
        m = self.HEADER_NAMES.match(f)
        if m.lastgroup:
          cData  [m.lastgroup] = c.getField( f )
          cHeader[m.lastgroup] = ( -1, f, True)
        else:
          cData  [f] = c.getField( f )
          cHeader[f] = ( -1, f, False)
      cData[bom.REFERENCE] = ref

      excluded = False
      for k, regex in exclude_filters.iteritems():
        value = cData.get(k)
        if value is not None:
          if regex.match(value):
            excluded = True
            break

      if not excluded:
        self.refs[ref] = cData
        self.header.update(cHeader)


class sch_bom(bom.bom):
  HEADER_NAMES = re.compile(')$|'.join(bom.bom.BOM_HEADER_ID_REGEXS + [''])
      , flags=re.I)

  def __init__(self, filename):
    bom.bom.__init__(self)
    self.meta[bom.SCHFILE] = self.meta[bom.SRCFILE] = [filename]

  def read(self, exclude_filters):
    if exclude_filters is None:
      exclude_filters = {}

    filename = self.getSrcFileName()

    with eeschematic.schCompIter(filename) as sch:
      for e, effRefs in sch:
        cData = {}
        cHeader = {}

        symbol = str(e.info.get(eeschematic.COMP_LIB))
        if symbol: 
          cData[bom.SYMBOL] = symbol

        for fields in e.info[eeschematic.COMP_FIELDS].itervalues():
          _fname = str(fields[eeschematic.FIELD_NAME ])
          _fval  = str(fields[eeschematic.FIELD_VALUE])

          m = self.HEADER_NAMES.match(_fname)
          if m.lastgroup:
            cData  [m.lastgroup] = _fval
            cHeader[m.lastgroup] = ( -1, _fname, True )
          else:
            cData  [_fname] = _fval
            cHeader[_fname] = ( -1, _fname, True )

        for ref in effRefs:
          data = cData.copy()
          data[bom.REFERENCE] = ref
          excluded = False
          for k, regex in exclude_filters.iteritems():
            value = data.get(k)
            if value is not None:
              if regex.match(value):
                excluded = True
                break

          if not excluded:
            self.refs[ref] = data
            self.header.update(cHeader)

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

  log.info("Test sch1 for convert direct sch to csv")
  main_cli(['--noopen'
    , 'test_files/sch1/sch1.sch'
    , 'test_files/sch1/test2_bom2csv.csv'
  ])

  os.system(' '.join(('sed -e "s/sch1-cache://g"'
  , 'test_files/sch1/sch1.csv'
  , '|' , 'sed -e "/^Date:/d"'
  , '|' , 'sed -e "/^Tool:/d"'
  , '>' , 'test_files/sch1/exp2_sch1.csv'
  )))

  actual = os.system(' '.join(('diff -s --strip-trailing-cr'
  , 'test_files/sch1/exp2_sch1.csv' 
  , 'test_files/sch1/test2_bom2csv.csv'
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
