#!/usr/bin/python
#
# This script is used under KiCad.pcbnew application and following
# intended method can be use on the pcbnew console:
#
#   clone()
#   replicateRefs()
#

import sys
import os.path
import os
import math

import pprint

import pcbnew

lib_path = os.path.join(os.path.dirname(__file__), '..')
lib_path = os.path.normpath(lib_path)
if lib_path not in sys.path:
  sys.path.append(lib_path)

from libs import eeschematic
from libs.pcbnew_misc import *

pp = pprint.PrettyPrinter(indent=2)


class equivalentNetlist:
  """This class help extract equivalent net from given set of equivalent Reference pairs
  """

  def __init__(self, modulePairs):
    self._pairs = modulePairs
    self._curPairsIdx = len(modulePairs)
    self._NetCodeToNetCode = {}

  def getEqvNetCode(self, netCode, netname = ''):
    eqvNetCode = self._NetCodeToNetCode.get(netCode, None)

    if eqvNetCode is not None:
      return eqvNetCode
    
    # Not in the NetCodeToNetCode map, then search of equivalent net by
    # go through pads of module pairs until find the equivalent net
    elif netCode not in self._NetCodeToNetCode:
      localNetCode = None
      while self._curPairsIdx>0:
        self._curPairsIdx -= 1
        module, eqvModule = self._pairs[self._curPairsIdx]
        eqvPads = iter(eqvModule.Pads())
        for pad in module.Pads():
          eqvPad = eqvPads.next()
          localNetCode = pad.GetNetCode()
          eqvNetCode = eqvPad.GetNetCode()
          self._NetCodeToNetCode[localNetCode] = eqvNetCode
          print "    %3s.%-2s and %s.%-2s suggest %15s map to %-15s" \
              % (    module.GetReference(),    pad.GetPadName()
                , eqvModule.GetReference(), eqvPad.GetPadName()
                ,       pad.GetShortNetname()
                ,    eqvPad.GetShortNetname()
                )
          if localNetCode==netCode:
            return eqvNetCode

      if (localNetCode!=netCode) and netname:
        self._NetCodeToNetCode[netCode] = None
        print "***ERROR*** Cannot find equivalent net of %s" % netname
        return None

class _helper:
  """ Set of functions use in this script
  """
  def __init__(self):
    pass

  def getInputList(self, msg):
    """ Obtain input from console and break them into a list using comma and space as delimit
    """
    tmp = raw_input(msg)
    tmp = tmp.replace(',' , ' ')
    tmp = tmp.strip()
    return tmp
  
  def cloneComponentNormal(self,  module, cloneModule, cloneOfs, rotation, cloneRotOrigin):
    modPos = module.GetPosition()
    if cloneModule.GetLayer() is not module.GetLayer():
      cloneModule.Flip(modPos)
    cloneModule.SetPosition(cloneOfs + modPos)
    cloneModule.SetOrientation(module.GetOrientation())
  
    if rotation!=0:
      cloneModule.Rotate(cloneRotOrigin, rotation)

  def cloneComponentVerMirror(self,  module, cloneModule, cloneOfs, srcRect ):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    modPos = module.GetPosition()

    if cloneModule.GetLayer() is not module.GetLayer():
      cloneModule.Flip(modPos)

    cloneLoc = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - modPos.x,
        cloneOfs.y + modPos.y)
    cloneModule.SetPosition(cloneLoc)
    cloneModule.SetOrientation(module.GetOrientation() + FromDeg(180))

  def cloneComponentHorMirror(self,  module, cloneModule, cloneOfs, srcRect ):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    modPos = module.GetPosition()

    if cloneModule.GetLayer() is not module.GetLayer():
      cloneModule.Flip(modPos)

    cloneLoc = pcbnew.wxPoint(
        cloneOfs.x + modPos.x ,
        cloneOfs.y + srcPos.y + srcEnd.y - modPos.y )
    cloneModule.SetPosition(cloneLoc)
    cloneModule.SetOrientation(module.GetOrientation())

  def cloneComponentDiaMirror(self,  module, cloneModule, cloneOfs, srcRect ):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    modPos = module.GetPosition()

    if cloneModule.GetLayer() is not module.GetLayer():
      cloneModule.Flip(modPos)

    cloneLoc = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - modPos.x,
        cloneOfs.y + srcPos.y + srcEnd.y - modPos.y)
    cloneModule.SetPosition(cloneLoc)
    cloneModule.SetOrientation(module.GetOrientation() + FromDeg(180))

  def cloneZoneNormal(self, cloneZone, cloneOfs, rotation, cloneRotOrigin):
    cloneZone.Move(cloneOfs)
    if rotation != 0:
      cloneZone.Rotate( cloneRotOrigin, rotation )

  def cloneZoneVerMirror(self, cloneZone, cloneOfs, srcRect):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    xAdj = cloneOfs.x + srcPos.x + srcEnd.x
    yAdj = cloneOfs.y
    for i in range(0, cloneZone.GetNumCorners()):
      corner = cloneZone.GetCornerPosition( i )
      corner = pcbnew.wxPoint( xAdj - corner.x, yAdj + corner.y )
      cloneZone.SetCornerPosition(i, corner )
    #OTHER WAY# srcPos = srcRect.GetPosition()

    #OTHER WAY# cloneZone.Mirror(srcPos)
    #OTHER WAY# cloneZone.Rotate(srcPos, FromDeg(180))
    #OTHER WAY# cloneLoc = pcbnew.wxPoint( \
    #OTHER WAY#     cloneOfs.x + srcRect.GetWidth(), \
    #OTHER WAY#     cloneOfs.y )
    #OTHER WAY# cloneZone.Move(cloneLoc)

  def cloneZoneHorMirror(self, cloneZone, cloneOfs, srcRect):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    xAdj = cloneOfs.x
    yAdj = cloneOfs.y + srcPos.y + srcEnd.y
    for i in range(0, cloneZone.GetNumCorners()):
      corner = cloneZone.GetCornerPosition( i )
      corner = pcbnew.wxPoint( xAdj + corner.x, yAdj - corner.y )
      cloneZone.SetCornerPosition(i, corner )

  def cloneZoneDiaMirror(self, cloneZone, cloneOfs, srcRect):
    srcPos = srcRect.GetPosition()
    srcEnd = srcRect.GetEnd()
    xAdj = cloneOfs.x + srcPos.x + srcEnd.x
    yAdj = cloneOfs.y + srcPos.y + srcEnd.y
    for i in range(0, cloneZone.GetNumCorners()):
      corner = cloneZone.GetCornerPosition( i )
      corner = pcbnew.wxPoint( xAdj - corner.x, yAdj - corner.y )
      cloneZone.SetCornerPosition(i, corner )

  def cloneTrackNormal(self,  cloneTrack, cloneOfs, rotation, cloneRotOrigin ):
    cloneTrack.Move(cloneOfs)
    if rotation !=0 :
      cloneTrack.Rotate(cloneRotOrigin, rotation)

  def cloneTrackVerMirror(self,  cloneTrack, cloneOfs, srcRect ):
    srcPos    = srcRect.GetPosition()
    srcEnd    = srcRect.GetEnd()
    trackStart= cloneTrack.GetStart()
    trackEnd  = cloneTrack.GetEnd()

    trackStart = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - trackStart.x,
        cloneOfs.y + trackStart.y )

    trackEnd = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - trackEnd.x,
        cloneOfs.y + trackEnd.y )

    cloneTrack.SetStart(trackStart)
    cloneTrack.SetEnd(trackEnd)

    #OTHER WAY# trackLayer = cloneTrack.GetLayer()
    #OTHER WAY# srcPos = srcRect.GetPosition()
    #OTHER WAY# 
    #OTHER WAY# cloneTrack.Flip(srcPos)
    #OTHER WAY# cloneTrack.Rotate( srcPos, FromDeg(180))
    #OTHER WAY# cloneTrack.SetLayer( trackLayer )
    #OTHER WAY# cloneLoc = pcbnew.wxPoint( \
    #OTHER WAY#     cloneOfs.x + srcRect.GetWidth(), \
    #OTHER WAY#     cloneOfs.y )
    #OTHER WAY# 
    #OTHER WAY# cloneTrack.Move(cloneLoc)

  def cloneTrackHorMirror(self,  cloneTrack, cloneOfs, srcRect ):
    srcPos    = srcRect.GetPosition()
    srcEnd    = srcRect.GetEnd()
    trackStart= cloneTrack.GetStart()
    trackEnd  = cloneTrack.GetEnd()

    trackStart = pcbnew.wxPoint(
        cloneOfs.x + trackStart.x ,
        cloneOfs.y + srcPos.y + srcEnd.y - trackStart.y)

    trackEnd = pcbnew.wxPoint(
        cloneOfs.x + trackEnd.x ,
        cloneOfs.y + srcPos.y + srcEnd.y - trackEnd.y)

    cloneTrack.SetStart(trackStart)
    cloneTrack.SetEnd(trackEnd)

  def cloneTrackDiaMirror(self,  cloneTrack, cloneOfs, srcRect ):
    srcPos    = srcRect.GetPosition()
    srcEnd    = srcRect.GetEnd()
    trackStart= cloneTrack.GetStart()
    trackEnd  = cloneTrack.GetEnd()

    trackStart = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - trackStart.x,
        cloneOfs.y + srcPos.y + srcEnd.y - trackStart.y)

    trackEnd = pcbnew.wxPoint(
        cloneOfs.x + srcPos.x + srcEnd.x - trackEnd.x,
        cloneOfs.y + srcPos.y + srcEnd.y - trackEnd.y)

    cloneTrack.SetStart(trackStart)
    cloneTrack.SetEnd(trackEnd)


def clone():
  """ Clone traces, zones, drawing, and location of equivalent components from selected components
  """
  __helper = _helper()

  # PCB file specification
  sch_rootfile= '' #r"C:\Projects\svn\Cricket\ECG\Rev0\PCB_KiCad\ModECG.sch"
  sch_dir     = ''
  sch_root    = ''
  pcb_file    = ''

  # clone Zone configuration
  #   cloneZoneLoc help identify which clone zone amount many
  cloneZoneLayer= pcbnew.Cmts_User  # one of pcbnew.LAYER_ID
  cloneZoneLoc  = None              # a pcbnew.wxPoint 

  # Clone configuration
  cloneX        = None
  cloneY        = None
  cloneArrayXdim= None
  cloneArraydX  = None
  cloneArraydY  = None
  cloneHorMirror= None # True or False
  cloneVerMirror= None # True or False

  #if len(sys.argv)>=2:
  #  sch_rootfile = sys.argv[1]
  #else:
  #  s = raw_input("Please enter LIB_DIR [" + sch_rootfile + "] ")
  #  if s: sch_rootfile = s
  
  if not sch_rootfile:
    board = pcbnew.GetBoard()
    cur_pcb_file = board.GetFileName()
    cur_pcb_file = cur_pcb_file.replace('/', os.sep)
    sch_rootfile = os.path.splitext(cur_pcb_file)[0] + '.sch'
    del board, cur_pcb_file
  else:
    sch_rootfile = sch_rootfile.replace('\\', os.sep)

  if not sch_dir : sch_dir  = os.path.dirname(sch_rootfile)
  if not sch_root: sch_root = os.path.basename(sch_rootfile)
  if not pcb_file: pcb_file = os.path.splitext(sch_root)[0] + '.kicad_pcb'

  ToUnit  = ToInch   if pcbnew.GetAbbreviatedUnitsLabel() == u'in' else ToMM
  FromUnit= FromInch if pcbnew.GetAbbreviatedUnitsLabel() == u'in' else FromMM

  if cloneZoneLoc is not None: cloneZoneLoc = FromUnit(cloneZoneLoc)

  del sch_rootfile
 
  
  #
  # Figure out switch PCB file we going to work on, and load it if not
  # already loaded
  #
  board = pcbnew.GetBoard()
  cur_pcb_file = board.GetFileName()
  cur_pcb_file = cur_pcb_file.replace('/', os.sep)
  pcb_fullpath = sch_dir+os.sep+pcb_file
  if pcb_fullpath.lower() != cur_pcb_file.lower():
    board = pcbnew.LoadBoard(pcb_file)
  else:
    pcb_file = os.path.basename(cur_pcb_file)
    sch_dir  = os.path.dirname(cur_pcb_file)
  del pcb_fullpath, cur_pcb_file
  print 'This clone script will apply on', pcb_file

  #
  # Find source areas for cloning
  #
  print 'Finding Cmts.User Zones for clone source'
  srcZones = []
  for i in range(0, board.GetAreaCount()):
    zone = board.GetArea(i)
    if zone.GetLayer() == cloneZoneLayer:
      srcZone = None
      if cloneZoneLoc is None:
        srcZone = zone
      elif zone.HitTestInsideZone(cloneZoneLoc):
        srcZone = zone

      if srcZone is not None:
        srcZones.append(srcZone)
        rect = srcZone.GetBoundingBox()
        print "Found source zone #" + str(len(srcZones)) \
            , "within", ToUnit(rect.GetOrigin()) \
            , "to", ToUnit(rect.GetEnd()) \

  if len(srcZones)==0:
    print "Can't find any source zone of %s Layer to clone" \
        % pcbnew.BOARD_GetStandardLayerName(cloneZoneLayer)
    return

  if len(srcZones)>1:
    i = int(raw_input("Please choose a zone #"))
    srcZone = srcZones[i]
  else:
    srcZone = srcZones[0]
  del srcZones
  srcRect = srcZone.GetBoundingBox()

  boardRect = board.ComputeBoundingBox(True)

  # Find components in srcRect and collect them into srcModules
  srcModules = {} # Dict of { Reference : pcbnew.MODULE }
  for module in board.GetModules():
    if module.HitTest(srcRect):
      ref = module.GetReference()
      srcModules[ref] = module

  print "Found following %d components in clone zone:" % len(srcModules)
  print "  " + ', '.join(srcModules.keys()) + "\n"
  
  # 
  # Extract REFToPath from schematic for figure out equivalent component for replicate 
  #
  print "Read schematic to find equivalent components for clone", sch_root
  eesch = eeschematic.schematic(sch_dir, True)
  eesch.LoadAllScheets(sch_root)
  #pp.pprint(eesch.GetSheets())
  eesch.LinkSheets()
  #pp.pprint(eesch.GetSheets())
  
  #eesch.GenREFToPathDict()
  #pp.pprint(eesch._REFToARPath)
  #pp.pprint(eesch._IDsToRefs)
  

  #
  # Figure out equivalent components
  #
  print "Figure out equivalent components and group them by channels"
  # Build AR Tree which contains equivalent REFs map
  arTree = eesch.BuildEqvRefsARTree(map(lambda x: x.encode(), srcModules.keys()))
  #pp.pprint(arTree._tree)

  # Group eqv REFs into channels 
  channels = arTree.groupByChannel(srcModules.keys())

  # Show WARNING to user if there is any
  for arPath, warnMsg in channels['WARN'].iteritems():
    print "*** WARN ***:", eesch.convertARPathToUserPath(arPath), warnMsg

  channels = channels['MAP']

  # Ask user what channel to clone ==> cloneChs (list of string)
  if len(channels)==0:
    print "*** ERROR *** Cannot find equivalent components for cloning"
    # TODO: Get a customized REFtoREF map from user some how
    cloneChs = []

  elif len(channels)>1:
    channel_names = channels.keys()
    channel_names = map(lambda x: [x, eesch.convertARPathToUserPath(x)], channel_names)
    channel_names.sort(key=lambda x: x[1])
    print "Found", len(channel_names), "channels: "
    for ch_idx, ch_name in enumerate(channel_names):
      print " ", ch_idx," -- ", ch_name[1]

    tmp  = __helper.getInputList(
        "Enter set of channels will be cloned [all channels if empty]: ")

    if tmp:
      cloneChs = []
      for ch in tmp.split(' '):
        if ch:
          cloneChs.append(channel_names[int(ch)][0])
    else:
      cloneChs = map(lambda x: x[0], channel_names)

  else:
    cloneChs = channels.keys()

  # ASK USER WHICH COMPONENT CAN BE USE AS CLONE ORIGIN ==> RefOfOrigin,
  # ModuleOfOrigin
  # (string)
  RefOfOrigin = raw_input("Which component can be use as clone origin? [None]")
  if RefOfOrigin.lower() in ('none'): 
    RefOfOrigin = ''
    ModuleOfOrigin = None
  else:
    RefOfOrigin = RefOfOrigin.decode()
    if not RefOfOrigin in srcModules:
      print "*** ERROR *** Cannot find " + RefOfOrigin +" in list of components for cloning"
      RefOfOrigin=''
      ModuleOfOrigin = None
      return
    ModuleOfOrigin = board.FindModuleByReference(RefOfOrigin)
    cloneX = srcRect.GetPosition().x
    cloneY = srcRect.GetPosition().y

  if not RefOfOrigin:
    # ASK USER HOW TO PUT CLONE IN TO ARRAY ==> cloneArrayXdim,
    # cloneArraydX, cloneArraydY (int)
    ask = set()
    if cloneArrayXdim is None: 
      ask.add('Xdim')
      cloneArrayXdim= round(math.sqrt(len(cloneChs)))

    if cloneArraydX   is None: 
      ask.add('dY')
      cloneArraydX  = srcRect.GetWidth() + FromInch(0.1)

    if cloneArraydY   is None: 
      ask.add('dX')
      cloneArraydY  = srcRect.GetHeight() + FromInch(0.1)

    if len(cloneChs)>1:
      if 'Xdim' in ask:
        tmp = __helper.getInputList(
            "Enter number of clones in X direction [%d]:" \
            % (cloneArrayXdim))
        if tmp: cloneArrayXdim = int(tmp)
      
      tmp = [ '', '' ]
      if cloneArrayXdim < len(cloneChs):
        if cloneArrayXdim > 1:
          #Ask for X and Y spacing between clone
          if ('dX' in ask) or ('dY' in ask):
            tmp = __helper.getInputList(
                "X and Y spacing between clones [%f, %f]: " \
                % (ToUnit(cloneArraydX), ToUnit(cloneArraydY)) )
            tmp = tmp.split(' ') + [ '', '' ]
        else:
          #Ask for Y spacing between clone
          if ('dY' in ask):
            tmp = __helper.getInputList(
                "Y spacing between clones [%f]: " \
                % (ToUnit(cloneArraydY)) )
            tmp = ['', tmp]
      else: 
        if cloneArrayXdim > 1:
          # Ask for X spacing between clone
          if ('dX' in ask):
            tmp = __helper.getInputList(
                "X spacing between clones [%f]: " %
                (ToUnit(cloneArraydX)) )
            tmp = [tmp, '']

      if tmp[0]: cloneArraydX = FromUnit(float(tmp[0]))
      if tmp[1]: cloneArraydY = FromUnit(float(tmp[1]))

    # ASK USER CLONE START LOCATION ==> cloneX, cloneY (int)
    ask = False
    if cloneX is None: 
      ask = True
      cloneX = srcRect.GetPosition().x + cloneArraydX

    if cloneY is None: 
      ask = True
      cloneY = srcRect.GetPosition().y

    if ask:
      tmp = __helper.getInputList(
          "Clone start point (%f, %f): " %
          (ToUnit(cloneX), ToUnit(cloneY)))
      tmp = tmp.split(' ') + [ '', '' ]

      if tmp[0]: cloneX = FromUnit(float(tmp[0]))
      if tmp[1]: cloneY = FromUnit(float(tmp[1]))

    if (cloneVerMirror is None) or (cloneHorMirror is None):
      tmp = raw_input("Ver/Hor/Dia Mirror? (Ver, Hor, Dia, [None]) :")
      if not tmp: tmp = 'no'
      tmp2 = tmp.lower()
      if tmp2 in ('no', 'none'):
        cloneVerMirror = False
        cloneHorMirror = False
      elif tmp2 in ('ver', 'vertical'):
        cloneHorMirror = False
        cloneVerMirror = True
      elif tmp2 in ('hor', 'horizontal'):
        cloneHorMirror = True
        cloneVerMirror = False
      elif tmp2 in ('dia', 'diagonal'):
        cloneVerMirror = True
        cloneHorMirror = True
      else:
        print "*** ERROR *** Not recognized answer of", tmp
        return

  # ASK USER TO CLEANUP THE CLONING AREAS ==> CleanUp (True/False)
  CleanUp = raw_input("Do you want to cleanup the clone target areas? (Yes/[No]/Cleanup Only) ").lower()
  NoClone = False
  if not CleanUp:
    CleanUp = False
  elif CleanUp in ('no'):
    CleanUp = False
  elif CleanUp in ("yes"):
    CleanUp = True
  elif CleanUp in ("cleanup only"):
    CleanUp = True
    NoClone = True
  else:
    print "*** ERROR *** Not recognized answer of", CleanUp
    CleanUp = False
    return


  # Collecting tracks that belong clone zone
  tracks = board.GetTracks()
  allTracks = []
  srcTracks = []
  for track in tracks:
    if track.HitTest(srcRect):
      srcTracks.append(track)
    else:
      allTracks.append(track)
  print "Found %d track in clone zone" % len(srcTracks)

  # Collecting Zones that belong clone zone
  srcZoneIdx = board.GetAreaIndex(srcZone)
  allZones = []
  srcZones = []
  for i in range(0, board.GetAreaCount()):
    if i != srcZoneIdx:
      zone = board.GetArea(i)
      if zone != srcZone:
        if zone.HitTest(srcRect):
          srcZones.append(zone) 
        else:
          allZones.append(zone)
  print "Found %d zones in clone zone" % len(srcZones)

  # Collecting Drawings that belong clone zone
  srcDrawings = []
  allDraws = []
  for drawing in board.GetDrawings():
    if drawing.HitTest(srcRect):
      srcDrawings.append(drawing)
    else:
      allDraws.append(drawing)
  print "Found %d drawings in clone zone" % len(srcDrawings)

  #
  # Start to do cloning work
  #
  if not RefOfOrigin:
    curCloneX = cloneX - srcRect.GetPosition().x
    curCloneY = cloneY - cloneArraydY - srcRect.GetPosition().y

  srcSize     = pcbnew.wxSize( srcRect.GetWidth(), srcRect.GetHeight() )
  srcSize90Deg= pcbnew.wxSize( srcRect.GetHeight(), srcRect.GetWidth() )

  #CloneLayers = set([pcbnew.B_Cu, pcbnew.F_Cu])

  xCnt = 0
  wxPointX0Y0 = pcbnew.wxPoint(0, 0)
  for cloneCh in cloneChs:
    print "Cloning channel", eesch.convertARPathToUserPath(cloneCh)
    REFtoREF = channels[cloneCh]

    # Figure out the clone origin
    if RefOfOrigin:
      # Using RefOfOrigin if supplied by user
      #
      cloneRefOfOrigin = REFtoREF.get(RefOfOrigin,None)
      if cloneRefOfOrigin is None:
        print "   *** WARN *** Cannot find equivalent origin reference in channel", cloneCh
        continue
      cloneModuleOfOrigin = board.FindModuleByReference(cloneRefOfOrigin)

      rotation   = round(cloneModuleOfOrigin.GetOrientation() - ModuleOfOrigin.GetOrientation())
      while (rotation<-1800): rotation += 3600
      while (rotation>+1800): rotation -= 3600

      cloneRotOrigin= cloneModuleOfOrigin.GetPosition()
      curCloneOfs   = cloneRotOrigin - ModuleOfOrigin.GetPosition()

    else:
      # Using CloneX and CloneY supplied by user
      #
      if xCnt == 0:
        xCnt = 0
        curCloneX = cloneX - srcRect.GetPosition().x
        curCloneY+= cloneArraydY
      else:
        curCloneX+= cloneArraydX

      curCloneOfs   = pcbnew.wxPoint(curCloneX, curCloneY)
      rotation      = 0
      cloneRotOrigin= srcRect.GetPosition()
    #EndOf if RefOfOrigin
    
    if CleanUp:
      cloneRect   = pcbnew.EDA_RECT( srcRect.GetPosition() + curCloneOfs , srcSize )
      if rotation!=0:
        cloneRect = cloneRect.GetBoundingBoxRotated( cloneRotOrigin, rotation )
      
      # Clean the Traces in cloning target
      for idx in range(len(allTracks)-1,-1,-1):
        track = allTracks[idx]
        if track.HitTest(cloneRect):
          #if track.GetLayer() in CloneLayers:
            allTracks.pop(idx)
            tracks.Remove(track)

      # Clean zones that belong cloning target
      for idx in range(len(allZones)-1,-1,-1):
        zone = allZones[idx]
        if zone.HitTest(cloneRect):
          allZones.pop(idx)
          board.Delete(zone)

      # Clean drawings that belong cloning target
      for idx in range(len(allDraws)-1,-1,-1):
        drawing = allDraws[idx]
        if drawing.HitTest(cloneRect):
          allDraws.pop(idx)
          board.Delete(drawing)
    #Endof if CleanUp


    if not NoClone:
      # Cloning the components
      print "  Moved Eqv. Modules"
      pairs = []
      for ref, module in srcModules.iteritems():
        cloneRef = REFtoREF.get(ref, None)

        if cloneRef is None:
          print "   *** WARN *** %s don't have equivalent components. Skip clone" \
              % ref
          continue

        cloneModule = board.FindModuleByReference(cloneRef)
        if cloneModule is None: 
          print "    *** ERROR *** Cannot find module with reference of", cloneRef
          continue

        if cloneHorMirror:
          if cloneVerMirror:
            __helper.cloneComponentDiaMirror(module, cloneModule, curCloneOfs, srcRect )
          else:
            __helper.cloneComponentHorMirror(module, cloneModule, curCloneOfs, srcRect )
        elif cloneVerMirror:
          __helper.cloneComponentVerMirror( module, cloneModule, curCloneOfs, srcRect )
        else:
          __helper.cloneComponentNormal( module, cloneModule, curCloneOfs, rotation, cloneRotOrigin )
        pairs.append([module, cloneModule])

      eqvNets = equivalentNetlist(pairs)

      # Cloning the Traces
      print "  Clone traces"
      for track in srcTracks:
        cloneNetCode = eqvNets.getEqvNetCode(
            track.GetNetCode(), track.GetShortNetname())
        if cloneNetCode is not None:
          #if track.GetLayer() in CloneLayers:
            cloneTrack = track.Duplicate()
            cloneTrack.SetNetCode(cloneNetCode)
            if cloneHorMirror:
              if cloneVerMirror:
                __helper.cloneTrackDiaMirror(cloneTrack,curCloneOfs,srcRect )
              else:
                __helper.cloneTrackHorMirror(cloneTrack,curCloneOfs,srcRect)
            elif cloneVerMirror:
              __helper.cloneTrackVerMirror(cloneTrack,curCloneOfs,srcRect)
            else:
              __helper.cloneTrackNormal(cloneTrack, curCloneOfs, rotation, cloneRotOrigin)
            tracks.Append(cloneTrack)
      
      # Cloning the drawing
      print "  Clone drawings"
      for drawing in srcDrawings:
        cloneDrawing = drawing.Duplicate()
        cloneDrawing.Move(curCloneOfs)
        board.Add(cloneDrawing)
      
      # Cloning the Zones
      print "  Clone zones"
      curPairsIdx = len(pairs)
      for zone in srcZones:
        # Figure out what is appropriate eqv netname for copper filled zone
        if zone.IsOnCopperLayer():
          cloneNetCode = eqvNets.getEqvNetCode(
              zone.GetNetCode(), zone.GetShortNetname())
          if cloneNetCode is not None:
            cloneZone = zone.Duplicate()
            cloneZone.SetNetCode(cloneNetCode)
          else:
            continue
        else:
          cloneZone = zone.Duplicate()

        if cloneHorMirror:
          if cloneVerMirror:
            __helper.cloneZoneDiaMirror(cloneZone, curCloneOfs, srcRect)
          else:
            __helper.cloneZoneHorMirror(cloneZone, curCloneOfs, srcRect)
        elif cloneVerMirror:
          __helper.cloneZoneVerMirror(cloneZone, curCloneOfs, srcRect)
        else:
          __helper.cloneZoneNormal(cloneZone, curCloneOfs, rotation, cloneRotOrigin)
        board.Add(cloneZone)
    #Endof if not NoClone

    # Advancing to next clone location
    xCnt += 1
    if xCnt >= cloneArrayXdim: 
      xCnt = 0
    
    #End for loop of cloneChs

def replicateRefs():
  """ Replicate the references' position for equivalent components from selected components
  """
  __helper = _helper()

  # PCB file specification
  sch_rootfile= '' #r"C:\Projects\svn\Cricket\ECG\Rev0\PCB_KiCad\ModECG.sch"
  sch_dir     = ''
  sch_root    = ''
  pcb_file    = ''

  # clone Zone configuration
  #   cloneZoneLoc help identify which clone zone amount many
  cloneZoneLayer= pcbnew.Cmts_User  # one of pcbnew.LAYER_ID
  cloneZoneLoc  = None              # a pcbnew.wxPoint 

  #if len(sys.argv)>=2:
  #  sch_rootfile = sys.argv[1]
  #else:
  #  s = raw_input("Please enter LIB_DIR [" + sch_rootfile + "] ")
  #  if s: sch_rootfile = s
  
  if not sch_rootfile:
    board = pcbnew.GetBoard()
    cur_pcb_file = board.GetFileName()
    cur_pcb_file = cur_pcb_file.replace('/', os.sep)
    sch_rootfile = os.path.splitext(cur_pcb_file)[0] + '.sch'
    del board, cur_pcb_file
  else:
    sch_rootfile = sch_rootfile.replace('\\', os.sep)

  if not sch_dir : sch_dir  = os.path.dirname(sch_rootfile)
  if not sch_root: sch_root = os.path.basename(sch_rootfile)
  if not pcb_file: pcb_file = os.path.splitext(sch_root)[0] + '.kicad_pcb'

  ToUnit  = ToInch   if pcbnew.GetAbbreviatedUnitsLabel() == u'in' else ToMM
  FromUnit= FromInch if pcbnew.GetAbbreviatedUnitsLabel() == u'in' else FromMM

  if cloneZoneLoc is not None: cloneZoneLoc = FromUnit(cloneZoneLoc)

  del sch_rootfile
 
  
  #
  # Figure out switch PCB file we going to work on, and load it if not
  # already loaded
  #
  board = pcbnew.GetBoard()
  cur_pcb_file = board.GetFileName()
  cur_pcb_file = cur_pcb_file.replace('/', os.sep)
  pcb_fullpath = sch_dir+os.sep+pcb_file
  if pcb_fullpath.lower() != cur_pcb_file.lower():
    board = pcbnew.LoadBoard(pcb_file)
  else:
    pcb_file = os.path.basename(cur_pcb_file)
    sch_dir  = os.path.dirname(cur_pcb_file)
  del pcb_fullpath, cur_pcb_file
  print 'This clone script will apply on', pcb_file

  #
  # Find source areas for cloning
  #
  print 'Finding Cmts.User Zones for clone source'
  srcZones = []
  for i in range(0, board.GetAreaCount()):
    zone = board.GetArea(i)
    if zone.GetLayer() == cloneZoneLayer:
      srcZone = None
      if cloneZoneLoc is None:
        srcZone = zone
      elif zone.HitTestInsideZone(cloneZoneLoc):
        srcZone = zone

      if srcZone is not None:
        srcZones.append(srcZone)
        rect = srcZone.GetBoundingBox()
        print "Found source zone #" + str(len(srcZones)) \
            , "within", ToUnit(rect.GetOrigin()) \
            , "to", ToUnit(rect.GetEnd()) \

  if len(srcZones)==0:
    print "Can't find any source zone of %s Layer to clone" \
        % pcbnew.BOARD_GetStandardLayerName(cloneZoneLayer)
    return

  if len(srcZones)>1:
    i = int(raw_input("Please choose a zone #"))
    srcZone = srcZones[i]
  else:
    srcZone = srcZones[0]
  del srcZones
  srcRect = srcZone.GetBoundingBox()

  boardRect = board.ComputeBoundingBox(True)

  # Find components in srcRect and collect them into srcModules
  srcModules = {} # Dict of { Reference : pcbnew.MODULE }
  for module in board.GetModules():
    if module.HitTest(srcRect):
      ref = module.GetReference()
      srcModules[ref] = module

  print "Found following %d components in clone zone:" % len(srcModules)
  print "  " + ', '.join(srcModules.keys()) + "\n"
  
  # 
  # Extract REFToPath from schematic for figure out equivalent component for replicate 
  #
  print "Read schematic to find equivalent components for clone", sch_root
  eesch = eeschematic.schematic(sch_dir, True)
  eesch.LoadAllScheets(sch_root)
  eesch.LinkSheets()

  #
  # Figure out equivalent components
  #
  print "Figure out equivalent components and group them by channels"
  # Build AR Tree which contains equivalent REFs map
  arTree = eesch.BuildEqvRefsARTree(map(lambda x: x.encode(), srcModules.keys()))

  # Group eqv REFs into channels 
  channels = arTree.groupByChannel(srcModules.keys())

  # Show WARNING to user if there is any
  for arPath, warnMsg in channels['WARN'].iteritems():
    print "*** WARN ***:", eesch.convertARPathToUserPath(arPath), warnMsg

  channels = channels['MAP']

  # Ask user what channel to clone ==> cloneChs (list of string)
  if len(channels)==0:
    print "*** ERROR *** Cannot find equivalent components for cloning"
    # TODO: Get a customized REFtoREF map from user some how
    cloneChs = []

  elif len(channels)>1:
    channel_names = channels.keys()
    channel_names = map(lambda x: [x, eesch.convertARPathToUserPath(x)], channel_names)
    channel_names.sort(key=lambda x: x[1])
    print "Found", len(channel_names), "channels: "
    for ch_idx, ch_name in enumerate(channel_names):
      print " ", ch_idx," -- ", ch_name[1]

    tmp  = __helper.getInputList(
        "Enter set of channels will be cloned [all channels if empty]: ")

    if tmp:
      cloneChs = []
      for ch in tmp.split(' '):
        if ch:
          cloneChs.append(channel_names[int(ch)][0])
    else:
      cloneChs = map(lambda x: x[0], channel_names)

  else:
    cloneChs = channels.keys()

  #
  # Start to do cloning work
  #
  for cloneCh in cloneChs:
    print "Cloning reference position of channel", eesch.convertARPathToUserPath(cloneCh)
    REFtoREF = channels[cloneCh]

    # Cloning the components
    for ref, module in srcModules.iteritems():
      cloneRef = REFtoREF.get(ref, None)

      if cloneRef is None:
        print "   *** WARN *** %s don't have equivalent components. Skip clone" \
            % ref
        continue

      cloneModule = board.FindModuleByReference(cloneRef)
      if cloneModule is None: 
        print "    *** ERROR *** Cannot find module with reference of", cloneRef
        continue

      cloneOrientation = cloneModule.GetOrientation()
      cloneModule.SetOrientation(module.GetOrientation())

      # Copy Reference Location
      refText      = module.Reference()
      cloneRefText = cloneModule.Reference()
      cloneRefText.SetPosition(refText.GetPosition() - module.GetPosition() + cloneModule.GetPosition())
      cloneRefText.SetOrientation(refText.GetOrientation())
      
      cloneModule.SetOrientation(cloneOrientation)
    #End for loop of cloneChs




