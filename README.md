# Summary
A set of scripts can be use to work with KiCad

* bom_plugins/bom2sch.py: Update eeschema symbol fields from CSV BOM file.
  Make a minimal change on .sch file, so we can diff it after.
* bom_plugins/bom2csv.py: Transform xml netlist to CSV BOM file. It
  create two table for un-grouped, and grouped versions.
