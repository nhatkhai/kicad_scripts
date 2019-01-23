import pcbnew


def ToMM(a):
  if isinstance(a, pcbnew.wxPoint): 
    return pcbnew.wxPoint(pcbnew.ToMM(a.x)
                         ,pcbnew.ToMM(a.y)) 
  else:
    return pcbnew.ToMM(a)


def ToInch(a):
  if isinstance(a, pcbnew.wxPoint): 
    return pcbnew.wxPoint(pcbnew.ToMils(a.x/1000.0)
                         ,pcbnew.ToMils(a.y/1000.0)) 
  else:
    return pcbnew.ToMils(a/1000.0)


def FromMM(a):
  if isinstance(a, pcbnew.wxPoint): 
    return pcbnew.wxPoint(pcbnew.FromMM(a.x)
                         ,pcbnew.FromMM(a.y)) 
  else:
    return pcbnew.FromMM(a)


def FromInch(a):
  if isinstance(a, pcbnew.wxPoint): 
    return pcbnew.wxPoint(pcbnew.FromMils(a.x*1000.0)
                         ,pcbnew.FromMils(a.y*1000.0)) 
  else:
    return pcbnew.FromMils(a*1000.0)


def FromDeg(a):
  return a * 10.0

