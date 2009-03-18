
from pypy.lang.fundy.cell_graph import BuiltinNode, IntNode, StringNode,    \
    CharNode, Cell

from pypy.lang.fundy.utils import Enum

ASSOC = Enum('LEFT', 'RIGHT', 'NONE')
FIXITY = Enum('PREFIX', 'INFIX', 'POSTFIX')

from pypy.lang.fundy.context import Context, OperatorRecord

class UnaryBuiltinNode(BuiltinNode):
    def __init__(self, func, arg=None):
        self.func = func

    def apply(self, argument):
        argument.reduce_WHNF()
        return self.func(argument)

    def instantiate(self, replace_this_cell, with_this_cell):
        return self


class BinaryBuiltinNode(BuiltinNode):
    def __init__(self, func, arg1=None, arg2=None):
        self.func = func
        self.arg1 = arg1
        self.arg2 = arg2

    def apply(self, argument):
        if not self.arg1:
            arg1 = argument
            arg2 = self.arg2
        elif not self.arg2:
            arg1 = self.arg1
            arg2 = argument
        else:
            assert False    # should be impossible

        if arg1 and arg2:
            # have enough arguments to apply the builtin, reduce them
            # to make sure they are value nodes, then call self.func
            arg1.reduce_WHNF()
            arg2.reduce_WHNF()
            return self.func(arg1, arg2)
        else:
            return BinaryBuiltinNode(self.func, arg1, arg2)

    def instantiate(self, replace_this_cell, with_this_cell):
        if self.arg1:
            arg1 = self.arg1.instantiate(replace_this_cell, with_this_cell)
        else:
            arg1 = None
        if self.arg2:
            arg2 = self.arg2.instantiate(replace_this_cell, with_this_cell)
        else:
            arg2 = None

        if arg1 is self.arg1 and arg2 is self.arg2:
            return self     # no need to make a new copy
        else:
            return BinaryBuiltinNode(self.func, arg1, arg2)


_types_dict = {'int': IntNode,
               'string': StringNode,
               'char': CharNode,
              }

def _get_typecheck_func(typ):
    """
    NOT_RPYTHON:
    """
    node_class = _types_dict[typ]
    return lambda cell: isinstance(cell.node, node_class)


def _get_extract_func(typ):
    """
    NOT_RPYTHON:
    """
    node_class = _types_dict[typ]
    getter = getattr(node_class, 'get_' + typ)
    return lambda cell: getter(cell.node)

def _get_box_func(typ):
    """
    NOT_RPYTHON:
    """
    node_class = _types_dict[typ]
    return lambda v: node_class(v)


class OpTable(object):
    """
    NOT_RPYTHON:
    """
    def __init__(self):
        self._db = {}

    def op(self, name=None, arg_types=None, ret_type=None,
           assoc=None, prec=None, fixity=None):
        """
        NOT_RPYTHON: returns a decorator that will make a builtin
        node out of a function, and register it in the OpTable. The function
        should operate on python level values; the decorator will wrap the
        function in code to unbox and typecheck the arguments and box the
        return result.
        NOTE: the returned decorator is also not RPython, but the wrapper
        function that it returns is, provided the function it is applied to is.
        """
        if isinstance(arg_types, str):
            default_type = arg_types
            arg_types = []
        elif arg_types is None:
            arg_types = []
        
        if ret_type is None:
            ret_type = default_type
            
        
        def decorator(func):
            """
            NOT_RPYTHON: 
            """
            num_params = func.func_code.co_argcount
            if len(arg_types) < num_params:
                _arg_types = arg_types + \
                    [default_type] * (num_params - len(arg_types))
            else:
                _arg_types = arg_types[:num_params]

            box = _get_box_func(ret_type)

            # note: annoying _ names are to avoid making the outer variables
            # inherited from OpTable.op be interpreted as locals by assigning
            # to them
            if name is None:
                _name = func.func_name
            else:
                _name = name

            if num_params == 1:
                argcheck = _get_typecheck_func(_arg_types[0])
                extract = _get_extract_func(_arg_types[0])

                def wrapper(x):
                    if argcheck(x):
                        raw_ret = func(extract(x))
                        ret = box(raw_ret)
                        return ret
                    else:
                        raise TypeError     # TODO: proper exception here
                # end def wrapper

                wrapper.func_name = _name
                cell = Cell(UnaryBuiltinNode(wrapper))
                if fixity is None:
                    _fixity = FIXITY.PREFIX

            elif num_params == 2:
                argcheck1, argcheck2 = map(_get_typecheck_func, _arg_types)
                extract1, extract2 = map(_get_extract_func, _arg_types)

                def wrapper(arg1, arg2):
                    if argcheck1(arg1) and argcheck2(arg2):
                        raw_ret = func(extract1(arg1), extract2(arg2))
                        ret = box(raw_ret)
                        return ret
                    else:
                        raise TypeError     # TODO: proper exception here
                # end def wrapper

                wrapper.func_name = _name
                cell = Cell(BinaryBuiltinNode(wrapper))
                if fixity is None:
                    _fixity = FIXITY.INFIX

            else:
                raise NotImplementedError

            if assoc is None:
                _assoc = ASSOC.LEFT
            else:
                _assoc = assoc

            if prec is None:
                _prec = 0
            else:
                _prec = prec
            
            self.register_name(_name, cell, _assoc, _prec, _fixity)

            return cell
        # end def decorator

        return decorator
    # end def OpTable.op

    def register_name(self, name, graph, assoc, prec, fixity):
        record = OperatorRecord(graph, assoc, prec, fixity)
        if not name in self._db:
            self._db[name] = set()
        self._db[name].add(record)

    def make_context(self):
        c = Context()
        for name, recordset in self._db.items():
            for r in recordset:
                c.bind_operator(name, r.graph, r.assoc, r.prec, r.fixity)
        return c


ops = OpTable()

@ops.op(name='+', arg_types='int', prec=0)
def plus(x, y):
    return x + y

@ops.op(name='-', arg_types='int', prec=0)
def plus(x, y):
    return x - y

@ops.op(name='*', arg_types='int', prec=10)
def plus(x, y):
    return x * y

@ops.op(name='/', arg_types='int', prec=10)
def plus(x, y):
    return x // y

@ops.op(arg_types='int', prec=20)
def neg(x):
    return -1 * x

default_context = ops.make_context()
    
