#!/usr/bin/python
#
# This script reset footprint field of all component in all schematic file
# back to component lib setting.
#
# python reset_sch_footprint [SCH_DIR] [LIB_DIR]
#
import os
import glob
import sys


def main():
  sch_dir = ''
  library_dir = ''
  if len(sys.argv)>=2:
    sch_dir = sys.argv[1]
  else:
    s = raw_input("Please enter SCH_DIR [" + sch_dir + "] ")
    if s: sch_dir =s

  if len(sys.argv)>=3:
    library_dir = sys.argv[2]
  else:
    s = raw_input("Please enter LIB_DIR [" + library_dir + "] ")
    if s: library_dir = s

  sch_out_dir = sch_dir + "_new"

  def_footprint = GetComponentFootprints(library_dir)

  if not os.path.exists(sch_out_dir):
    os.makedirs(sch_out_dir)

  for sch_file in glob.glob(os.path.join(sch_dir, "*.sch")):
    print "Process file ", sch_file
    file_out = os.path.basename(sch_file)
    file_out = os.path.join(sch_out_dir, file_out)
    ResetDefaultFootprint(sch_file, file_out, def_footprint)

  print "Result can be find in ", sch_out_dir


def GetComponentFootprints(library_dir):
    # Extract footprint field (F2) from library into def_footprint
    def_footprint = {}
    cur_comp = ""
    for lib in glob.glob(os.path.join(library_dir, "*.lib")):
        for line in open(lib):
            items = line.split(" ")
            if   items[0]=="DEF":
                cur_comp=items[1]
                if cur_comp[0]=="~": cur_comp=cur_comp[1:]
            elif items[0]=="F2" : 
                def_footprint[cur_comp]=items[1]
    return def_footprint


def ResetDefaultFootprint(sch_file, file_out, def_footprint):
    lineCnt = 0
    cur_comp = ""
    fout = open(file_out, 'w+')
    for line in open(sch_file):
        # Process a line
        items = line.split(" ")
        if   items[0]=="L": cur_comp = items[1]
        elif items[0]=="F" and items[1]=="2":        
            if cur_comp in def_footprint:
                items[2] = def_footprint[cur_comp]
                print "Assign ", items[2], " to ", cur_comp
        fout.write(" ".join(items))
        lineCnt = lineCnt + 1

    fout.close()


if __name__ == "__main__":
  main()
