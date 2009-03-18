
import re
import sys

import py

from pypy.lang.fundy.cell_graph import Builtin, StringNode, CharNode, IntNode, ASSOC



# this moderately awful regexp is supposed to match one or more backslashes
# at the end of a string, to be used in split_separator to tell whether a
# separator was backslash-escaped
end_slashes = re.compile(r'.*(?<!\\)(?P<slashes>(\\)+)$')
def split_separator(line, sep):
    """
    Splits a string on a given separator that may be escaped by a backslash
    (the backslash may also be escaped), returns a list of the split parts,
    with any escaping backslashes removed (note that a sequence of backslashes
    that does not occur before the separator is unmolested).
    """
    parts = line.split(sep)
    
    # now have to find parts whose ends are escaped and join them to the next    
    i = 0
    while i < len(parts) - 1:
        m = end_slashes.match(parts[i])
        if m:
            # need to replace the trailing sequence of slashes with half the
            # number of slashes (rounded down), to account for backslash-escaped
            # backslashes, and the rounding down (if the number was odd) removes
            # the backslash that was escaping the separator
            n_slashes = len(m.group('slashes'))
            resolved_slashes = '\\' * (n_slashes // 2)
            if n_slashes % 2 == 0:
                parts[i] = parts[i][:-1 * n_slashes] + resolved_slashes
            else:
                parts[i] = ''.join([parts[i][:-1 * n_slashes], resolved_slashes,
                                    sep, parts[i + 1]])
                del parts[i+1]
        else:
            i += 1

    return parts

return_types_dict = {'int': 'IntNode', 'str': 'StringNode', 'char':CharNode}
def make_op(name, params, types, return_type, python_exp, assoc, prec):
    """
    Makes a builtin function and wraps it in a BUILTIN node.The generated
    function automatically unwraps its arguments before passing them to the
    given expression and wraps the returned value again.
    
    name        the name of the builtin
    params      a list of the parameter names of the function
    types       a list of the type names of the parameters
    python_exp  a python expression using the parameters, but acting on
                interp-level objects, not wrapped app-level objects
    assoc       the associativity of the builtin operator
    prec        the precedence of the builtin operator 
    """
    defstr = 'def op(%s):' % ', '.join(params)
    convert = '\n'.join(['    %s = %s.%sval' % (arg, arg, typ)
                         for arg, typ in zip(params, types)])
    retstr = '    return %s(%s)' % (return_types_dict[return_type], python_exp)
    
    exec ('\n'.join([defstr, convert, retstr]))
    
    op.func_name = name
    return Builtin(assoc=assoc, prec=prec, code=op)
    

def make_builtins_from_table(tablefilename):
    """
    NOT_RPYTHON: this function reads the builtin table format and makes the
    appropriate function definitions (which manipulate wrapped objects rather
    that python objects), creates a builtin node for each, and returns them
    as a dictionary mapping builtin names to the builtin nodes
    """
    f = open(tablefilename)
    lines = f.readlines()
    f.close()
    
    d = {}
    prec = sys.maxint // 2
    blanks = 0
    continuation = ''
    for line in lines:
        # handle lines ending with a \
        if continuation:
            line = continuation + line
        if line.endswith('\\\n'):
            continuation = line[:-2]
            continue
        else:
            continuation = None
        
        # 3 or more blank lines in a row identifies a new priority class
        if not line.strip():
            blanks += 1
            continue
        else:
            if blanks >= 3:
                prec -= 1000000
            blanks = 0
        
        # lines starting with a # are comments
        if line.startswith('#'):
            continue
        
        fundy_exp, rest = split_separator(line, '::')
        type_exp, python_exp = split_separator(rest, '-->')
        
        # TODO: support more than just unary and binary-infix operators
        parts = map(str.strip, fundy_exp.split())
        if len(parts) == 3:
            # binary infix operator
            arg1, op, arg2 = map(str.strip, fundy_exp.split())
            args = [arg1, arg2]
            # TODO: more sophisticated associativity specification
            if arg1 < arg2:
                assoc = ASSOC.LEFT
            else:
                assoc = ASSOC.RIGHT
        elif len(parts) == 2 and len(parts[0]) == 1 and parts[0].islower():
            # unary postfix operator
            arg, op = parts
            # TODO: allow unary operators to specify associativity
            assoc = ASSOC.LEFT
        elif len(parts) == 2 and len(parts[1]) == 1 and parts[1].islower():
            # unary prefix operator
            op, arg = parts
            args = [arg1]
            # TODO: allow unary operators to specify associativity
            assoc = ASSOC.RIGHT
        else:
            assert False, "only unary operators and binary infix operators " \
                          "supported at the moment"
        
        # TODO: support more complicated type expressions
        types = map(str.strip, type_exp.split('->'))
        return_type = types.pop()
        
        d[op] = make_op(op, args, types, return_type, python_exp, assoc, prec)
    # end for line in lines
    
    return d
# end def make_builtins_from_table


opsfile = py.magic.autopath().dirpath().join('fundy.ops').strpath
default_context = make_builtins_from_table(opsfile)
