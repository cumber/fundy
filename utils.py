
from pypy.rlib.objectmodel import CDefinedIntSymbolic


class EnumVal(CDefinedIntSymbolic):
    """
    Instances behave as CDefinedIntSymbolic, but have a symbolic name
    representation useful when debugging on top of CPython
    """
    def __init__(self, name, expr):
        CDefinedIntSymbolic.__init__(self, expr)
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'EnumVal(%r, %d)' % (self.name, self.expr)


class Enum(object):
    """
    Instances have a set of EnumVals
    """
    def __init__(self, *symbols):
        i = 0
        for s in symbols:
            setattr(self, s, EnumVal(s, i))
            i += 1
    
    def __repr__(self):
        return 'Enum(%s)' %  \
                ', '.join([repr(k)
                           for k in self.__dict__ 
                           if isinstance(getattr(self, k), EnumVal)])
