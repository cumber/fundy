
from pypy.rlib.objectmodel import CDefinedIntSymbolic


class Enum(CDefinedIntSymbolic):
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
        return 'Enum(%r, %d)' % (self.name, self.expr)


def MakeEnums(*symbols):
    """
    Returns a list of Enums with the given string names
    """
    i = 0
    ret = []
    for s in symbols:
        ret.append(Enum(s, i))
        i += 1
    return ret

def DefineEnums(*names, **kwargs):
    """
    NOT_RPYTHON: util function to define enums; pass scope as a keyword argument
    to define a module/class/instance or a dictionary to define the Enums in,
    with the same names as their symbolic values (scope defaults to globals()
    as seen in the function definition, which is not very useful)
    """
    try:
        scope = kwargs['scope']
        if type(scope) is not dict:
            scope = scope.__dict__
    except KeyError:
        scope = globals()
        
    symbolics = MakeEnums(*names)
    for i in xrange(len(names)):
        scope[names[i]] = symbolics[i]
