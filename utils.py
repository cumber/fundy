#
#   Copyright 2009 Benjamin Mellor
#
#   This file is part of Fundy.
#
#   Fundy is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from pypy.rlib.objectmodel import CDefinedIntSymbolic, r_dict

# XXX: Had to stop using the following definition for EnumVal, as the
# translation process was producing errors about trying to hash a Symbolic.
# I think it was trying to optimise an if/elif/else chain using a hashmap.
#
#class EnumVal(CDefinedIntSymbolic):
#    """
#    Instances behave as CDefinedIntSymbolic, but have a symbolic name
#    representation useful when debugging on top of CPython
#    """
#    def __init__(self, name, expr):
#        CDefinedIntSymbolic.__init__(self, expr)
#        self.name = name
#
#    def __str__(self):
#        return self.name
#
#    def __repr__(self):
#        return 'EnumVal(%r, %d)' % (self.name, self.expr)

class EnumVal(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'EnumVal(%r)' % self.name


class Enum(object):
    """
    Instances have a set of EnumVals
    """
    def __init__(self, *symbols):
        for s in symbols:
            setattr(self, s, EnumVal(s))

    def __repr__(self):
        return 'Enum(%s)' %  \
                ', '.join([repr(k)
                           for k in self.__dict__
                           if isinstance(getattr(self, k), EnumVal)])


class rset(object):
    """
    An RPython implementation of sets.

    XXX: Currently the internal representation is a hacky deferral to a
    dictionary with all values being None.

    XXX: Currently the program can only make use of a single type of rset.
    """
    def __init__(self, key_eq, key_hash, elems=[]):
        self._store = r_dict(key_eq, key_hash)
        for e in elems:
            self._store[e] = None

    def __contains__(self, elem):
        return elem in self._store
    contains = __contains__

    def add(self, elem):
        self._store[elem] = None

    def list(self):
        ret = []
        for k in self._store:
            ret.append(k)
        return ret

    def __iter__(self):
        return self._store.iterkeys()

    def __repr__(self):
        """
        NOT_RPYTHON:
        """
        return '{' + ', '.join(map(repr, self._store.keys())) + '}'


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
    already_seen = set()
    for thing in things:
        content.extend(thing.dot(already_seen))
    content.append('}')
    dotcode = '\n'.join(content)

    from subprocess import Popen, PIPE

    child = Popen(['python', 'xdot.py', '-'], stdin=PIPE)
    child.stdin.write(dotcode)
    child.stdin.close()

    import py
    py.path.local('/tmp/dot.dot').write(dotcode)



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


class LabelledGraph(object):
    """
    Generates dot code for a graph with a label node pointing to the graph.

    Can be initialised *either* of two ways:

    1) with eval and astexpr, in which case the abstract syntax tree (which
       should be an expression node) is turned into a textual label (a bit ugly,
       since it's kind of an unparse just after we parsed it, but it's quite
       lightweight since we assume we only deal with expressions and Symbols,
       and Symbols can be directly converted to text), and the graph is
       generated by dispatching the ast in the Eval.

    2) by specifying the label and the graph directly.
    """
    def __init__(self, eval=None, astexpr=None, label=None, graph=None):
        """
        NOT_RPYTHON:
        """
        if graph is not None:
            self.graph = graph
            self.label = label
        else:
            self.graph = eval.dispatch(astexpr)
            self.label = self.make_label(astexpr)

    def dot(self, already_seen=None):
        """
        NOT_RPYTHON:
        """
        if already_seen is None:
            already_seen = set()

        yield dot_node(id(self.label), shape='box', color='blue',
                       label=self.label)
        yield dot_link(id(self.label), self.graph.nodeid(), color='blue')
        for dot in self.graph.dot(already_seen):
            yield dot

    @staticmethod
    def make_label(node):
        """
        NOT_RPYTHON: Make a textual description of an AST expression.
        """
        if node.symbol == 'expr':
            frags = []
            for n in node.children:
                if n.symbol == 'expr':
                    frags.append('(%s)' % LabelledGraph.make_label(n))
                else:
                    frags.append(LabelledGraph.make_label(n))
            return ' '.join(frags)
        elif node.symbol == 'typeswitch':
            expr = node.children[0]
            cases = node.children[1:]
            frags = ['typeswitch %s:'
                     % LabelledGraph.make_label(expr)]
            for case in cases:
                # All n should be switchcase with 2 children
                frags.append('case %s return %s'
                             % (LabelledGraph.make_label(case.children[0]),
                                LabelledGraph.make_label(case.children[1])))
            return '\\n'.join(frags)
        elif hasattr(node, 'additional_info'):
            return node.additional_info.replace('"', '\\"')
        else:
            return node.symbol


class FundyPreparer(object):
    def __init__(self):
        self.preparation_funcs = []

    def register(self, preparation_func):
        self.preparation_funcs.append(preparation_func)

    def prepare(self, for_translation):
        for func in self.preparation_funcs:
            func(for_translation)

# This object can be imported from any module and used to register a function
# that should be called to switch backand forth between translated and
# untranslated modes. This allows debugging of the code that gets translated
# without actually translating it.
# If necessary this could be extended in future with other parameters.
preparer = FundyPreparer()
