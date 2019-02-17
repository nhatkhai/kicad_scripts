# Summary
A set of scripts can be use to work with KiCad

* bom_plugins/bom2sch.py: Update eeschema symbol fields from the first
  table found in CSV BOM file. It will make a minimal change on .sch files.
  Allow simple diff tools make sense.

* bom_plugins/bom2csv.py: Transform xml netlist or root .sch file to CSV
  BOM file. It create two tables for un-grouped, and grouped versions.

* eeschema/reset_footprint.py: Reset all the symbol footprint back to
  default value from libraries

* pcbnew/clone.py: Clone multi-channels layout using schematic hierarchy,
  and Cmts.User zones as marker for clone area.

* convertors/modToPretty.py: Convert old mod file into pretty file.
* convertors/pcb_downgrade.py: Down grade .kicad_pcb or .kicad_mod file
  save by 5.x so that it can be open on 4.x or 5.x

