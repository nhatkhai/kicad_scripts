#!/usr/bin/python
"""
@package: Parser and capture eeschema components and hierarchy into memory

"""
import os
import re
import logging

from utils      import MapNestedList, MapNestedDict
from linkeddata import linkedVirtualStrData, linkedStrData

log = logging.getLogger(__name__)

SHEET_ID    = 'ID'
SHEET_FILE  = 'FILE'
SHEET_NAME  = 'NAME'

COMP_LIB    = 'Lib'
COMP_REF    = 'Ref'
COMP_PART   = 'Part'
COMP_ID     = 'ID'
COMP_AR     = 'AR'
COMP_FIELDS = 'Fields'
FIELD_VALUE = 'Value'
FIELD_NUMBER= 'Number'
FIELD_POSX  = 'X'
FIELD_POSY  = 'Y'
FIELD_NAME  = 'Name'
FIELD_FLAGS = 'Flags'

FIELD_REF_NAME  = 'Reference'
FIELD_VAL_NAME  = 'Value'
FIELD_FP_NAME   = 'Footprint'
FIELD_PDF_NAME  = 'Datasheet'


class schematic:
  """
  This class capture eeschema components and hierarchy into memory
  
  It shall create a set of following nested dictionary to help describe,
  and navigate information of schematic:

    Component information,
    Sheet information, their hierarchy 

    # Top level data that allow to access to all data of the whole
    # eeschema schematic
    A_SCHEMATIC_DATA = { 
      ''                           : A_SHEET_DATA(ROOT_SCHEMATIC), 
      str(RELATIVE_SHEET_FILENAME1): A_SHEET_DATA,
      str(RELATIVE_SHEET_FILENAME2): A_SHEET_DATA,
      ...
      str(RELATIVE_SHEET_FILENAMEn): A_SHEET_DATA,
    }
 
    # A data structure capture info of a single schematic file
    A_SHEET_DATA = {
      'sheets' : { 
        str(RELATIVE_SHEET_FILENAME1): A_SHEET_ID_INFO,
        str(RELATIVE_SHEET_FILENAME2): A_SHEET_ID_INFO,
        ...
        str(RELATIVE_SHEET_FILENAMEn): A_SHEET_ID_INFO,
      },
      'sheetIDs' : {  
        str(SHEET_UNIQUE_ID1) : A_SHEET_ID_INFO,
        str(SHEET_UNIQUE_ID2) : A_SHEET_ID_INFO,
        ...
        str(SHEET_UNIQUE_IDn) : A_SHEET_ID_INFO,
      },
      'Components': A_COMPONENTS_DATA,
    }
 
    # A data structure capture a hierarchy block info
    A_SHEET_ID_INFO = {
      'NAME' : str(SHEET_NAME),
      'LINK' : A_SHEET_DATA, # Generate by self.LinkSheets()
    }

    # A data structure capture component's info of a single schematic file
    A_COMPONENTS_DATA = { 
      str(ID1): {
        'Lib'   : str(COMPONENT_LIBARAY_NAME), 
        'Ref'   : str(COMPONENT_DEFAULT_REFERENCE),
        'Part'  : str(COMPONENT_DEFAULT_PART_NUMBER),
        'AR'    : { 
          str(AR_PATH1) : { 
            'Ref' : str(COMPONENT_REFERENCE),
            'Part': str(COMPONENT_PART_NUMBER),
          },
          str(AR_PATH2) : {...}
          ...
          str(AR_PATHn) : {...}
        },
        'Fields': { 
          str(FIELDS_NUMBER1) : { 
            'Name' : str(Field_Name), 
            'Value': str(Field_Value),
          },
          str(FIELDS_NUMBER2) : {...},
          ...
          str(FIELDS_NUMBERn) : {...},
        },
      },
      str(ID2): {...},
      ...
      str(IDn): {...},
    }

    A_REFTOARPATH = { 
      str(COMPONENT_REFERENCE1) : { 
        'ID'       : str(ID),
        'USER_PATH': str(USER_PATH),
        'AR_PATH'  : str(AR_PATH), 
      },
      str(COMPONENT_REFERENCE2) : {..},
      ...
      str(COMPONENT_REFERENCEn) : {..},
    }

    A_IDSTOREFS = { 
      str(ID1) : set(COMPONENT_REFERENCE),
      str(ID2) : set(COMPONENT_REFERENCE),
      ...
      str(IDn) : set(COMPONENT_REFERENCE),
    }
  """

  def __init__(self, sch_dir
               , extractComponents=False):
    """
    @param sch_dir; (str) root path of schematic files
    """
    self._sch_dir = sch_dir

    self._sheets      = {}  # A_SCHEMATIC_DATA 
    self._REFToARPath = {}  # A_REFTOARPATH 
    self._IDsToRefs   = {}  # A_IDSTOREFS
    self._extractComponents     = extractComponents      # True will extract component references information.

  def GetSheets(self):
    """Obtain A_SCHEMATIC_DATA
    """
    return self._sheets

  def GetREFtoARPath(self):
    """Obtain A_REFTOARPATH
    """
    if len(self._REFToARPath)==0: self.GenREFToPathDict()
    return self._REFToARPath

  def GetIDstoREFs(self):
    """Obtain A_IDSTOREFS
    """
    if len(self._IDsToRefs)==0: self.GenREFToPathDict()
    return self._IDsToRefs

  def LoadASheet(self, sch_file):
    """Extract sub sheets and components data from schematic file

    @param sch_file: (str) schematic file that going to be processed
    @return A_SHEET_DATA
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
    """Load all sub sheets, components information into memory
    
    @param sch_root:  (str) root schematic file that going to be processed
    @return A_SCHEMATIC_DATA
    """

    def __loadScheets(sch_root_inner):
      """Extract sub sheets, and components information from all schematic
      files relative to specified sch_root, return a set of A_SHEET_DATA
      
      @param sch_root_inner: (str) schematic file name
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
    """Generate a map from component's References to the most top AR PATH
    
    @return None. Update self._REFToARPath, self._IDsToRefs
    """

    def __genREFToPathDict(sch, ar_path='', user_path=''):
      # Extract component in the sch, and update the REFToARPath
      # mapping to make sure is link to the highest sheet level
      for compID, info in sch['Components'].iteritems():
        new_ar_path  = ar_path + '/' + compID
        arDict = info['AR']
        if new_ar_path in arDict: comInfo = arDict[new_ar_path]
        else                    : comInfo = info
        ref = comInfo['Ref']
        new_user_path=user_path
        old_ar_path = self._REFToARPath.get(ref, {}).get('AR_PATH')
        if old_ar_path is None:
          self._REFToARPath[ref] = { 
              'AR_PATH': new_ar_path, 
              'USER_PATH': new_user_path, 
              'ID': compID 
          }
        elif len(new_ar_path) < len(old_ar_path):
          self._REFToARPath[ref] = { 
              'AR_PATH': new_ar_path, 
              'USER_PATH': new_user_path, 
              'ID': compID 
          }
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
    """Convert AR Path to a User Path using hierarchy sheet names

    @param arPath: (str) AR path. /5ABCDA/AE123
    @return (str) path of hierarchy sheet names. /Analog1/Out3
    """
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
  """This class help map equivalent references and group by ARPATH

    A_REFTOREF_GROUPED_BY_CHANNEL = { 
      'MAP' : {
        str(ARPATH1) : A_REFTOREF,
        str(ARPATH2) : A_REFTOREF,
        ...
        str(ARPATHn) : A_REFTOREF,
      },
      'NOTCOVERED': set(COMPONENT_REFERENCE),
      'REFTOREF'  : A_REFTOREF,
      'WARN'      : { 
        str(ARPATH1) : str(Warning_message),
        str(ARPATH2) : str(Warning_message),
        ...
        str(ARPATHn) : str(Warning_message),
      },
    }

    A_REFTOREF = {
      str(COMPONENT_REFERENCE1) : str(EQUIVALENT_COMPONENT_REFERENCE),
      str(COMPONENT_REFERENCE2) : str(EQUIVALENT_COMPONENT_REFERENCE),
      ...
      str(COMPONENT_REFERENCEn) : str(EQUIVALENT_COMPONENT_REFERENCE),
    }
    
    A_AR_SUB_TREE = { 
      'ARPath'   : [str(SHEET_ID)],
      'children' : { 
        str(SHEET_ID1) : A_AR_SUB_TREE 
        str(SHEET_ID2) : A_AR_SUB_TREE 
        ...
        str(SHEET_IDn) : A_AR_SUB_TREE 
      },
      'REFtoREF' : A_REFTOREF,
    }

  """

  def __init__(self, aschematic, refs):
    self._schem= aschematic
    self._tree = {  # A_AR_SUB_TREE
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
    """Add a map entry ref to eqvRef into A_AR_SUB_TREE

    @param arPath: (str) ARPATH to the sub sheet
    @param ref: (str) Original component reference
    @param eqvRef: (str) Equivalent component reference to ref
    """

    def _getPath(IDs, iCurPath, curIDidx=0):
      """Create all children if in in the tree, and return children of
      specified in IDs list

      @param IDs: (list of str) list of SHEET_IDs that make up ARPATH 
      @param iCurPath: (A_AR_SUB_TREE) of the root sheet
      @param curIDidx: (int) A index point to a SHEET_ID in IDs

      @return (A_AR_SUB_TREE) of the sheet from the path specified in
              IDs path (ARPATH)
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
    """ Build A_REFTOREF_GROUPED_BY_CHANNEL

    @param refNeedToCover: (set, list, or tuple) of component references
            that will be use to find other equivalent component references
    
    Travel through the tree. Extract ARPATH that reach refNeedToCover, and
    build A_REFTOREF_GROUPED_BY_CHANNEL dictionary

    @return A_REFTOREF_GROUPED_BY_CHANNEL
    """

    def _groupByChannel(curPath, refToBeCovered, refToRef=None):
      """A Traveler, and builder for A_REFTOREF_GROUPED_BY_CHANNEL

      @param curPath: (A_AR_SUB_TREE)
      @param refToBeCovered: (set of str) set of component references to be
                             covered
      @param refToRef: (A_REFTOREF) is a accumulated A_REFTOREF map of from
                       root down to and include parent of curPath

      @return A_REFTOREF_GROUPED_BY_CHANNEL
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

    # Implement of groupByChannel method is start here
    if not isinstance(refNeedToCover, set): 
      refNeedToCover = set(refNeedToCover)

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
      tmp[FIELD_NUMBER]  = linkedStrData(items, 3)
      tmp[FIELD_POSX]    = linkedStrData(items, 9)
      tmp[FIELD_POSY]    = linkedStrData(items, 11)
      tmp[FIELD_FLAGS]   = linkedStrData(items, 15)
      if len(items)>=22:
        tmp[FIELD_NAME]  = linkedStrData(items, 21)
      else:
        tmp[FIELD_NAME]  = linkedVirtualStrData(
              { '0': FIELD_REF_NAME,  # Default KiCad field name
                '1': FIELD_VAL_NAME,
                '2': FIELD_FP_NAME,
                '3': FIELD_PDF_NAME,
                }.get(items[3], 'Field' + items[3])
            , items, 20
            )

    return self

  def duplicate(self, info, insertLocation=None):
    """ Clone current info and insert is into raw for later save back to
    the file

    @param info: (dict) A nested dict with leaves element are
            baseLinkedData object

    @return duplicated info
    """
    def _clone(x):
      a = x.getSrc()
      new_a = cloned_array.setdefault(id(a), [])
      if not new_a:
        new_a.extend(a)
        if insertLocation:
          insertLocation.getSrc().append(new_a)
        else:
          a.append(new_a)

      return x.clone(new_a)

    # Clone all the original items
    cloned_array = {}
    return MapNestedDict(info, _clone)


class schMapper(schIter):
  """ This is eeschema iterative mapping 

  It allow map the infile to outfile with a customized transforming
  """

  def __init__(self, infile, outfile):
    schIter.__init__(self, infile)
    self.outfile = outfile

  def _clearData(self):
    MapNestedList(self.raw, self.outfile.write)
    schIter._clearData(self)


# Test section for pytest style
#
def tests():
  log.info("Entering test mode")
  assert True
  import doctest
  doctest.testmod(verbose=True)

if __name__ == "__main__":
  tests()
