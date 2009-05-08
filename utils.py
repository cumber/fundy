
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


# some utility functions used for the dot-viewer capabilities, which cannot
# be used from the translated interpreter at the moment, so these functions
# do not have to be RPython
def dotview(*things):
    """
    NOT_RPYTHON: Displays graphs using PyGame.

    Expects all arguments to have a dot() method defined, which should be a
    generator yielding lines of dot format graph syntax. The dot() methods
    need not be RPython.
    """
    content = ["digraph G{"]
    for thing in things:
        content.extend(thing.dot())
    content.append('}')

    import py
    py.test.config.basetemp = py.path.local('/tmp')

    tmpfile = py.test.ensuretemp("fundy_graphs").join("tmp.dot")
    tmpfile.write('\n'.join(content))

    from dotviewer import graphclient
    graphclient.display_dot_file(tmpfile.strpath, wait=False)


def dict_to_params(d):
    """
    NOT_RPYTHON: Render a dict as a comma separated string: key="value"
    """
    return ', '.join(['%s="%s"' % key_value for key_value in d.items()])

def dot_node(node_id, **params):
    """
    NOT_RPYTHON: Render a dot node.
    """
    return '"%s" [%s];' % (node_id, dict_to_params(params))

def dot_link(from_id, to_id, **params):
    """
    NOT_RPYTHON: Render a dot link.
    """
    return '"%s" -> "%s" [%s];' % (from_id, to_id, dict_to_params(params))
