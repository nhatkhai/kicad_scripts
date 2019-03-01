# Example of run the script
* Open PCBNEW -> Tools -> Scripting Console. 
* Entering below commands after the ">>>" marks:
```
>>> cd <scriptfolder>
>>> import pcbnew.clone as m
>>> m.cloneRef()
+ This clone script will apply on ModXXX.kicad_pcb
| Finding Cmts.User Zones for clone source
| Found source zone #1 within (63, 73) to (94, 111)
| Found following 150 components in clone zone:
|   C701, C706, R630, R632, R712, R713, R710, R711, R716, R717, R714, R715, R718, R719, U502, U501, R709, R708, R705, R704, R707, R706, R701, R703, R702, D608, D606, D607, D604, D605, D602, D603, D601, U605, U604, U606, U601, U603, U602, C501, C502, C503, U704, U706, U707, U701, U702, U703, C610, C611, C612, C614, C615, C616, C617, C618, C619, D706, R604, R605, R606, R601, R602, R603, R608, R609, C603, C602, C601, C607, C606, C605, C604, C609, C608, R617, R616, R615, R614, R613, R612, R611, R610, C724, C725, C726, C720, C721, R619, R618, R501, R622, R623, R620, R621, R626, R627, R624, R625, R628, R629, C621, C620, C625, C624, C626, R734, R735, C708, C709, R730, R731, R732, R733, C702, C703, R636, R631, C707, C704, C705, R736, C715, C714, C717, C716, C711, C710, C712, C719, C718, R727, R726, R725, R724, R723, R722, R721, R720, R729, R728, D707, R635, D705, D704, D703, D702, D701, R634, D708
| 
| Read schematic to find equivalent components for clone ModXXX.sch
| Figure out equivalent components and group them by channels
| Found 4 channels: 
|   0  --  XXX0&1
|   1  --  XXX4&5
|   2  --  XXX6&7
|   3  --  XXX8&9
+ Enter set of channels will be cloned [all channels if empty]: 1 2 3
| Cloning reference position of channel XXX4&5
| Cloning reference position of channel XXX6&7
| Cloning reference position of channel XXX8&9
```
