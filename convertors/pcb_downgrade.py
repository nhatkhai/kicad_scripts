#!/bin/python
"""
Downgrade pcbnew or footprint file from 5.x so that 5.x, 4.0.7 can both
open it.
"""
import sys
import os
import logging
import re
import argparse

log = logging.getLogger(__name__)

def main_cli(argv=None):
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument('files', nargs='*', metavar='KICAD_PCB_FILE'
      , help = '''List of .kicad_pcb or .kicad_mod (Footprint) files 
      need to be downgraded''')
  p = p.parse_args(argv)

  # 5.x use offset in mm
  # 4.x use at in inch (4 decimal for nm precision)
  offset = re.compile(
      "\( *offset +\( *xyz +" 
                    "([-+]?\d+\.?\d*) +"
                    "([-+]?\d+\.?\d*) +"
                    "([-+]?\d+\.?\d*) *\) *\)"
      , flags = re.I)

  for pcbnew_file_name in p.files:
    log.info("Processing file %s", pcbnew_file_name);
    with open(pcbnew_file_name       , 'r') as inf \
        ,open(pcbnew_file_name+'.new', 'w') as outf :
      for aline in inf:
        aline = offset.sub(
          lambda m: "(at (xyz %.4f %.4f %.4f))" % (
            round(float(m.group(1))/25.4, 4),
            round(float(m.group(2))/25.4, 4),
            round(float(m.group(3))/25.4, 4),), aline)
        outf.write(aline);

    bakSchFile = pcbnew_file_name + '.bak'
    log.info("  Backup old file in %s", bakSchFile)
    os.rename(pcbnew_file_name, bakSchFile)
    os.rename(pcbnew_file_name + '.new', pcbnew_file_name)

#
# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=False)
  
  log.info("Test on sch1 and fps/test1 for normal use case")
  main_cli(['test_files/sch1/sch1.v5.kicad_pcb',
            'test_files/fps/test1.v5.kicad_mod',
  ])

  for f, ext in (('sch1/sch1', '.kicad_pcb'), 
                 ('fps/test1', '.kicad_mod'),):
    actual = os.system(' '.join(('diff -s --strip-trailing-cr'
      , 'test_files/%s.v5%s' % (f, ext)
      , 'test_files/%s.v4%s' % (f, ext)
    ,)))
    assert actual==0, \
        "diff[%d] - downgraded %s.v5.%s not match expected" \
        % (actual, f, ext)

  sys.exit(0)


if __name__ == "__main__":
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s [%(filename)s:%(lineno)-4d] %(levelname)7s - %(message)s')
  if '--test' in sys.argv: 
    tests()

  main_cli()
