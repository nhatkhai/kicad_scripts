#!/usr/bin/python
"""
This library read eeschema into data structure of

"""
import os
import shlex
import re
import logging

from linkeddata import linkedVirtualStrData, linkedStrData

log = logging.getLogger(__name__)

SHEET_ID  ='ID'
SHEET_FILE='FILE'
SHEET_NAME='NAME'

COMP_LIB  ='Lib'
COMP_REF  ='Ref'
COMP_PART ='Part'
COMP_ID   ='ID'
COMP_AR   ='AR'
COMP_FIELDS='Fields'
FIELD_VALUE='Value'
FIELD_NAME ='Name'

FIELD_REF_NAME  = 'Reference'
FIELD_VAL_NAME  = 'Value'
FIELD_FP_NAME   = 'Footprint'
FIELD_PDF_NAME  = 'Datasheet'


class schematic:
  """
  This class parse the KiCad schematic file, and extract information  such
  as:

    Component information,
    Sheet information, their hierarchy 

    A_SCHEMATIC_DATA = 
      { 
        ''                      : A_SHEET_TREE
        RELATIVE_SHEET_FILE_NAME: A_SHEET_DATA
      }
 
    A_SHEET_TREE = 
      {
        'sheets'    : { Schematic_File_Name: 
                          { Sheet_Unique_ID: 
                              { 
                                'NAME':Sheet_Name 
                                'LINK': A_SHEET_TREE
                              }
                          }
                      }
        'sheetIDs'  : 
          { 
            Sheet_Unique_ID : Point_To_Dict_Of_Sheet_Unique_ID 
          }
       'Components': A_COMPONENTS_DATA
      }
 
    A_SHEET_DATA = 
      {
        'sheets' : { Schematic_File_Name: 
                      { Sheet_Unique_ID: 
                          { 
                            'NAME':Sheet_Name 
                          }
                      }
                   }
        'sheetIDs' : 
          { 
            Sheet_Unique_ID : Point_To_Dict_Of_Sheet_Unique_ID 
          }
        'Components': A_COMPONENTS_DATA
      }
 
 
    A_COMPONENTS_DATA = 
      { ID: {'Lib'   : Component_Libaray_Name, 
             'Ref'   : Component_Default_Reference
             'Part'  : Component_Default_Part_Number
             'AR'    : { AR_PATH : 
                          { 'Ref' : Component_Default_Reference
                            'Part': Component_Default_Part_Number
                          }
                       }
             'Fields': { Fields_Number : { 'Name' : Field_Name, 
                                           'Value': Field_Value
                                         }
                       }
            } 
      }
  """

  def __init__(self, sch_dir
               , extractComponents=False):
    """
    @param sch_dir; (str) root path of schematic files
    """
    self._sch_dir = sch_dir

    self._sheets      = {}  # a set of A_SCHEMATIC_DATA 

    self._REFToARPath = {}  # dict of { Component_Reference : 
                            #           { 
                            #             'ID'       : Component_ID
                            #             'USER_PATH': USER_PATH, 
                            #             'AR_PATH'  : AR_PATH, 
                            #           } 
                            #         }
                            
    self._IDsToRefs   = {}  # Dict of { Component_ID : List of Component_References }

    self._extractComponents     = extractComponents      # True will extract component references information.

  def GetSheets(self):
    return self._sheets

  def GetREFtoARPath(self):
    if len(self._REFToARPath)==0: self.GenREFToPathDict()
    return self._REFToARPath

  def GetIDstoREFs(self):
    if len(self._IDsToRefs)==0: self.GenREFToPathDict()
    return self._IDsToRefs

  def LoadASheet(self, sch_file):
    """ Extract sub sheets and components data from schematic file, return A_SHEET_DATA

    Parameters:
      sch_file       [in]     string contain schematic file that going to be processed

    TODO: Use schIter for this
    """
    sheets  = {}
    sheetIDs= {}
    comps   = {}

    with open(os.path.join(self._sch_dir, sch_file)) as f:
      for e, state in schIter(f):
        if state == e.SUB_SCH_EX:
          _id   = str(e.info[SHEET_ID])
          sheetIDs[_id] = sheets.setdefault(str(e.info[SHEET_FILE])
            , {}  ).setdefault(_id
                , {'NAME' : str(e.info[SHEET_NAME])} )

        elif state == e.COMP_EX:
          _ref = str(e.info[COMP_REF])
          if _ref.startswith('#'):
            continue

          comps.setdefault(str(e.info[COMP_ID]), {
            'Lib' : str(e.info[COMP_LIB]),
            'Ref' : _ref,
            'Part': str(e.info[COMP_PART]),
            'AR'  : MapNestedDict(e.info[COMP_AR], str),
          })

    ret = { 'sheets' : sheets, 'sheetIDs' : sheetIDs }
    if self._extractComponents: 
      ret['Components'] = comps

    self._sheets[sch_file] = ret
    return ret

  def LoadAllScheets(self, sch_root):
    """Load all sub sheets, components information into memory, return a A_SCHEMATIC_DATA

    Parameters:
       sch_root [in]      string contain schematic file that going to be processed
    """

    def __loadScheets(sch_root_inner):
      """Extract sub sheets, and components information from all schematic
      files relative to specified sch_root, return a set of A_SHEET_DATA
      
      Parameters:
         sch_root [in]      string contain schematic file that going to be processed
         sheets   [in/out]  a A_SCHEMATIC_DATA structure where sheets[''] contain root sheet of A_SHEET_DATA
      """
      if sch_root_inner not in self._sheets:
        data = self.LoadASheet(sch_root_inner)
        for sch_file in iter(data['sheets']):
          __loadScheets(sch_file)

        # Update root schematic
        self._sheets[''] = data

    self._sheets      = {}
    self._REFToARPath = {}
    self._IDsToRefs   = {}
    return __loadScheets(sch_root)

  def LinkSheets(self):
    """Link all sub sheet structure together, by adding 'LINK' keys into
    each A_SHEET_DATA relative to specified sch_root
    """

    def _linkSheets(sch):
      """Link all sub sheet structure together, by adding 'LINK' keys into
      each A_SHEET_DATA relative to specified sch

      Parameters:
        sch [in] The top A_SHEET_DATA
      """
      
      for sheetFile, info in sch['sheets'].iteritems():
        for sheetID, sheetInfo in info.iteritems():
          if 'LINK' not in sheetInfo:
            next_sch = self._sheets[sheetFile]
            sheetInfo['LINK'] = next_sch
            _linkSheets(next_sch)

    _linkSheets(self._sheets[''])
    self._sheets['linked']=''

  def GenREFToPathDict(self):
    """Generate a map from component's References to the most top AR PATH,
    return REFToARPath dict of { Component_Reference : 
                                  { 'AR_PATH' : AR_PATH, 
                                    'USER_PATH': USER_PATH, 
                                    'ID' : Component_ID
                                  } 
                                }
           IDsToRefs  dict of { Component_ID : List of Component_References }
    """

    def __genREFToPathDict(sch, ar_path='', user_path=''):
      """Generate a map from component's References to the most top AR PATH,
      return REFToARPath dict of { Component_Reference : 
                                    { 'AR_PATH' : AR_PATH, 
                                      'USER_PATH': USER_PATH, 
                                      'ID' : Component_ID
                                    } 
                                  }
             IDsToRefs  dict of { Component_ID : List of Component_References }
      
      sch is a linked A_SHEET_DATA
      """
    
      # Extract component in the sch, and update the REFToARPath
      # mapping to make sure is link to the highest sheet level
      for compID, info in sch['Components'].iteritems():
        new_ar_path  = ar_path + '/' + compID
        arDict = info['AR']
        if new_ar_path in arDict: comInfo = arDict[new_ar_path]
        else                    : comInfo = info
        ref = comInfo['Ref']
        new_user_path=user_path
        old_ar_path = self._REFToARPath.get(ref, {'AR_PATH':None})['AR_PATH']
        if old_ar_path is None:
          self._REFToARPath[ref] = { 'AR_PATH': new_ar_path, 'USER_PATH': new_user_path, 'ID': compID }
        elif len(new_ar_path) < len(old_ar_path):
          self._REFToARPath[ref] = { 'AR_PATH': new_ar_path, 'USER_PATH': new_user_path, 'ID': compID }
        refs = self._IDsToRefs.setdefault(compID,set())
        refs.add(ref)

      for sheetFile, info in sch['sheets'].iteritems():
        for sheetID, sheetInfo in info.iteritems():
          new_ar_path  = ar_path + '/' + sheetID
          new_user_path= user_path + '/' + sheetInfo['NAME']
          __genREFToPathDict(sheetInfo['LINK'], new_ar_path, new_user_path)

    if 'linked' not in self._sheets: self.LinkSheets()
    __genREFToPathDict(self._sheets[''])

  def BuildEqvRefsARTree(self, refs):
    return ARTree(self, refs)

  def convertARPathToUserPath(self, arPath):

    if '' not in self._sheets: return ''
    if 'linked' not in self._sheets: self.LinkSheets()

    if isinstance(arPath, str): 
      sheetIDs = arPath.split('/')
    else: 
      sheetIDs = arPath

    user_Path = []
    sch = self._sheets['']
    for sheetID in sheetIDs:
      if sheetID:
        a = sch['sheetIDs'].get(sheetID)

        if a is not None:
          user_Path.append(a['NAME'])
          sch = a['LINK']
        else:
          # It may be component ID, if it is the last one in the list
          break

    return '/'.join(user_Path)


class ARTree:
  """This class help keep equivalent map of References to References end
  group them in to channels using ARPath

    A_AR_SUB_TREE = { 
      'ARPath'   : Path_of_this_current_sub_tree
      'children' : { sheet_ID : A_AR_SUB_TREE }
      'REFtoREF' : { component_REF : equivalent_component_REF }
                 }
    
    A_REFtoREF_GROUPED_BY_CHANNEL = { 
      'MAP' : { ARPATH : { Components_Ref : Equivalent_Component_Ref },
      'WARN': { ARPATH : Warning_message }
                                    }
  """

  def __init__(self, aschematic, refs):
    self._schem= aschematic
    self._tree = {
        'ARPath'   : [],
        'children' : {},
        'REFtoREF' : {},
                 }

    compIDsToREFs = aschematic.GetIDstoREFs()
    refsToARPath  = aschematic.GetREFtoARPath()

    for ref in refs:
      for eqvRef in iter(compIDsToREFs[refsToARPath[ref]['ID']]):
        if eqvRef != ref:
          pathInfo = refsToARPath[eqvRef]
          self.Add( pathInfo['AR_PATH'], ref, eqvRef )

  def Add(self, arPath, ref, eqvRef=''):
    """Add a map of ref to eqvRef into the tree15A66
    """

    def _getPath(IDs, iCurPath, curIDidx=0):
      """Create all children if in in the tree, and return children of
      specified in IDs list

      IDs is a list of of sheet_IDs in AR_PATH (top sheet ID at index 0)
      curPath is a A_AR_SUB_TREE
      """
      if curIDidx<len(IDs):
        ID = IDs[curIDidx]
        curIDidx += 1
        children = iCurPath['children']
        iCurPath  = children.setdefault(ID
            , {
                'ARPath'  : IDs[:curIDidx],
                'children': {},
                'REFtoREF': {},
              })
        return _getPath(IDs, iCurPath, curIDidx)
      else:
        return iCurPath

    # Implementation of Add method start here
    sheetIDs= arPath.split('/')[1:-1]
    curPath = _getPath(sheetIDs, self._tree)
    curPath['REFtoREF'][ref] = eqvRef

  def groupByChannel(self, refNeedToCover):
    """ Travel through the tree, and extract ARPATH that can covert all
    specified refNeedToCover, and return A_REFtoREF_GROUPED_BY_CHANNEL
    dictionary
      
    """

    def _groupByChannel(curPath, refToBeCovered, refToRef=None):
      """ Travel through the tree, and extract ARPATH that can covert all
      specified refNeedToCover, and return A_REFtoREF_GROUPED_BY_CHANNEL
      dictionary

      @param curPath is A_SHEET_TREE
      @param refToBeCovered is a set of component References to be covered
      @param refToRef is a accumulated REFtoREF map of from root down to and include parent of curPath

      @return A_REFtoREF_GROUPED_BY_CHANNEL
      """
      children    = curPath['children']
      pathRefToRef= curPath['REFtoREF']

      covered       = set(pathRefToRef.keys())
      curNotCovered = refToBeCovered - covered

      if refToRef is None:
        refToRef = {}
      curReftoRef= refToRef.copy()
      curReftoRef.update(pathRefToRef)

      # Found a equivalent channel?
      if len(curNotCovered)==0:
        ret = {
            'MAP' : { '/'.join(curPath['ARPath']): curReftoRef },
            'NOTCOVERED' : curNotCovered,
            'REFTOREF'   : curReftoRef,
            'WARN': {},
              }
      else:
        ret = {
            'MAP': {},
            'NOTCOVERED' : curNotCovered,
            'REFTOREF'   : curReftoRef,
            'WARN': {},
              }

      # Reach the end of the tree?
      if len(children)==0:

        # Reach the end, but not able to covered all requested References?
        if len(curNotCovered)!=0:
          # Warn user something may be wrong
          # Cannot find full covered on this path event we reach to the
          # bottom sheet
          ARPath = '/'.join(curPath['ARPath'])
          ret['WARN'][ARPath] = \
              "Cannot find all equivalent component(s) for " + ','.join(curNotCovered)
          if len(curNotCovered)*20 < len(curReftoRef)*100:
            ret['MAP'][ARPath] = curReftoRef
        
      # Still more children to go down?
      else:

        # We of covered all without go all the way to the bottom
        if len(curNotCovered)==0:
          # Warn user something may be wrong
          # All covered but not reach all the way to the bottom sheet
          ret['WARN']['/'.join(curPath['ARPath'])] = \
              "Already found all equivalent components without reach to lowest child sheet"

        #my_notCovered = curNotCovered.copy()
        #my_reftoRef   = curReftoRef.copy()
        pairtialCovered = []
        MAP = {}
        WARN= {}

        # Only add children that cover completely, once that not cover
        # completely, but in the MAP, and WARP buffere for later decision
        for sheetID, child in children.iteritems():
          child_ret = _groupByChannel(child, curNotCovered, curReftoRef)
          if len(child_ret['MAP'])!=0:
            if len(child_ret['NOTCOVERED'])==0:
              ret['MAP'].update(child_ret['MAP'])
              ret['WARN'].update(child_ret['WARN'])
            else:
              MAP.update(child_ret['MAP'])
              WARN.update(child_ret['WARN'])
              child_ret['ARPath'] = child['ARPath']
              pairtialCovered.append(child_ret)

        # Check if this parent page can cover from partial covered children
        for child_ret in pairtialCovered:
          childNotCovered = child_ret['NOTCOVERED']
          curNotCovered = curNotCovered.intersection(childNotCovered)
          curReftoRef.update(child_ret['REFTOREF'])
          if len(curNotCovered)==0:
            ret['MAP']['/'.join(curPath['ARPath'])] = curReftoRef
            MAP = {}
            WARN= {}
            break

        ret['NOTCOVERED'] = curNotCovered
        ret['REFTOREF']   = curReftoRef
        ret['MAP'].update(MAP)
        ret['WARN'].update(WARN)

      return ret

    # Implement of groupByChanned method is start here
    if not isinstance(refNeedToCover, set): refNeedToCover = set(refNeedToCover)
    return _groupByChannel(self._tree, refNeedToCover)


class schIter:
  """ This is a eeschema iterative parser.
  
  It allow process the large files in smaller chunk without store every
  thing in memory.
  """

  SUB_SCH_ENT = "Sheet"
  SUB_SCH_EX  = "SheetExit"
  COMP_ENT    = "Comp"
  COMP_EX     = "CompExit"

  ELM_RE = re.compile(
      '(?P<'+SUB_SCH_ENT +'>' r'\$Sheet'    r')$|'
      '(?P<'+SUB_SCH_EX  +'>' r'\$EndSheet' r')$|'
      '(?P<'+COMP_ENT    +'>' r'\$Comp'     r')$|'
      '(?P<'+COMP_EX     +'>' r'\$EndComp'  r')$|'
      , flags=re.I)

  # This is a token splitter which reserve all characters, space, and
  # detect text in double quote as one single token.
  SPLIT_RE = re.compile(r'\s+|(?:[^\s"]|"(?:\\.|[^"])*")+')

  def __init__(self, afile):
    self.file    = afile

    self.lineCnt  = 0  # Current processing line number
    self.stateFunc= lambda: None

    self.raw   = [] # Store a chunk of raw data from the file
    self.info  = {} # Store a extracted relevant data in dict style

    # Process functions for each keywords
    # Transition function by keyword
    self._stateFuncs = {
        self.SUB_SCH_ENT: self._SheetEnter,
        self.SUB_SCH_EX : self._SheetExit,
        self.COMP_ENT   : self._CompEnter,
        self.COMP_EX    : self._CompExit, 
        }

    # Functions call before file continue to be read
    # transition -> pre read file function
    self._preReadFuncs = {
        self._CompEnter : lambda: None,
        self._CompItem  : lambda: None,
        self._SheetEnter: lambda: None,
        self._SheetItem : lambda: None,
    }

    # Processing functions stack
    self._processor = [self._OtherItem]

  def __iter__(self):
    return self

  def next(self):
    self._preReadFuncs.get(self.stateFunc, self._clearData)()
    for line in self.file:
      self.lineCnt = self.lineCnt + 1

      # Split into words
      items = []
      if line[:1] != ' ':
        items.append('')

      for i in self.SPLIT_RE.finditer(line):
        items.append(i.group(0))

      self.raw.append(items)

      # Looking for a keywords for change process function
      m = self.ELM_RE.match(items[1])
      state = m.lastgroup
      self.stateFunc = self._stateFuncs.get(state, self._processor[-1])

      # Apply transition/process function
      return self.stateFunc(), state

    raise StopIteration

  def _clearData(self):
    self.raw   = [] # Store a chunk of raw data from the file
    self.info  = {} # Store a extracted relevant data in dict style

  def _SheetEnter(self):
    self._processor.append(self._SheetItem)
    return self

  def _SheetExit(self):
    if self._processor.pop() != self._SheetItem:
      raise ValueError("Line %d - Invalid Sheet Exiting" % self.lineCnt)
    return self

  def _CompEnter(self):
    self._processor.append(self._CompItem)
    return self

  def _CompExit(self):
    if self._processor.pop() != self._CompItem:
      raise ValueError("Line %d - Invalid Comp Exiting" % self.lineCnt)
    return self

  def _OtherItem(self):
    return self

  def _SheetItem(self):
    items = self.raw[-1]

    if   items[1]=='U':  # Sch unique ID
      self.info[SHEET_ID]   = linkedStrData(items, 3)
    elif items[1]=='F0': # Sch name
      self.info[SHEET_NAME] = linkedStrData(items, 3)
    elif items[1]=='F1': # Sch file name
      self.info[SHEET_FILE] = linkedStrData(items, 3)
    return self

  def _CompItem(self):
    items = self.raw[-1]

    if   items[1]=='L': # Component_Library Reference
      self.info[COMP_LIB] = linkedStrData(items, 3)
      self.info[COMP_REF] = linkedStrData(items, 5)

    elif items[1]=='U': # ComponentPart ?? ComponentID
      self.info[COMP_PART]= linkedStrData(items, 3)
      self.info[COMP_ID]  = linkedStrData(items, 7)

    elif items[1]=='AR': # Component_Path&ID Ref ComponentPart
      # Assume the line look like:
      # AR Path="THE_AR_PATH" Ref="THE_REF" Part="UNIT_NUMBER"
      # AR data { AR_PATH -> { COMP_REF, COMP_PART } }
      path = items[3][5:]
      tmp = self.info.setdefault(COMP_AR, {}).setdefault(path, {})
      tmp[COMP_REF]  = linkedStrData(items, 5, 4)
      tmp[COMP_PART] = linkedStrData(items, 7, 5)

    elif items[1]=='F': # Component_Fields
      # data is { FIELD_NUMBER -> { FIELD_VALUE, FIELD_NAME } }
      tmp = self.info.setdefault(COMP_FIELDS, {}).setdefault(items[3],{})
      tmp[FIELD_VALUE]   = linkedStrData(items, 5)
      if len(items)>=22:
        tmp[FIELD_NAME]  = linkedStrData(items, 21)
      else:
        tmp[FIELD_NAME]  = linkedVirtualStrData(
              { '0': FIELD_REF_NAME,  # Default KiCad field name
                '1': FIELD_VAL_NAME,
                '2': FIELD_FP_NAME,
                '3': FIELD_PDF_NAME,
                }.get(items[3], '')
            , items, 21
            )

    return self


class schMapper(schIter):
  """ This is eeschema iterative mapping 

  It allow map the infile to outfile with a customized transforming
  """

  def __init__(self, infile, outfile):
    schIter.__init__(self, infile)
    self.outfile = outfile

  def _clearData(self):
    for LineItems in self.raw:
      for item in LineItems:
        self.outfile.write(item)
    schIter._clearData(self)


def MapNestedDict(data, func):
  """Map a nested dictionary with specified func

  @example:
  >>> a                      = {"a": {"b": 1 , "c": 2 }, "d": 3 }
  >>> MapNestedDict(a, str) == {'a': {'b':'1', 'c':'2'}, 'd':'3'}
  True
  """
  if not isinstance(data, dict):
    return func(data)

  return {k:MapNestedDict(e, func) for k, e in data.items()}


# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  tests()
