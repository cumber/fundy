"""
This module defines builtin Fundy functions that are defined using Python code.
"""

from graph import BuiltinNode, NodePtr
from utils import Enum, dot_node, dot_link
from builtin import IntNode, CharNode, StringNode, unit_type, unit, \
                    bool_type, bool_false, bool_true

ASSOC = Enum('LEFT', 'RIGHT', 'NONE')
FIXITY = Enum('PREFIX', 'INFIX', 'POSTFIX')

from context import Context, OperatorRecord


class UnaryBuiltinNode(BuiltinNode):
    def __init__(self, func, arg=None):
        BuiltinNode.__init__(self)
        self.func = func

    def apply(self, argument):
        argument.reduce_WHNF_inplace()
        return self.func(argument)

    def instantiate(self, replace_this_ptr, with_this_ptr):
        return self


class BinaryBuiltinNode(BuiltinNode):
    def __init__(self, func, arg1=None, arg2=None):
        BuiltinNode.__init__(self)
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
            arg1.reduce_WHNF_inplace()
            arg2.reduce_WHNF_inplace()
            return self.func(arg1, arg2)
        else:
            return BinaryBuiltinNode(self.func, arg1, arg2)

    def instantiate(self, replace_this_ptr, with_this_ptr):
        if self.arg1:
            arg1 = self.arg1.get_instantiated_node_ptr(replace_this_ptr,
                                                       with_this_ptr)
        else:
            arg1 = None
        if self.arg2:
            arg2 = self.arg2.get_instantiated_node_ptr(replace_this_ptr,
                                                       with_this_ptr)
        else:
            arg2 = None

        if arg1 is self.arg1 and arg2 is self.arg2:
            return self     # no need to make a new copy
        else:
            return BinaryBuiltinNode(self.func, arg1, arg2)

    def dot(self, already_seen=None):
        """
        NOT_RPYTHON:
        """
        for dot in super(BinaryBuiltinNode, self).dot(already_seen):
            yield dot

        if self.arg1:
            for dot in self.arg1.dot():
                yield dot
            yield dot_link(self.nodeid(), self.arg1.nodeid(),
                           color='blue', label='1')

        if self.arg2:
            for dot in self.arg2.dot():
                yield dot
            yield dot_link(self.nodeid(), self.arg2.nodeid(),
                           color='blue', label='2')

# end class BinaryBuiltinNode

class TypeTable(object):
    def __init__(self):
        self.boxfuncs = {}
        self.extractfuncs = {}
        self.typecheckfuncs = {}

    def add_simple_type(self, name, nodeclass):
        self.boxfuncs[name] = lambda v: nodeclass(v)
        getter = nodeclass.make_getter()
        self.extractfuncs[name] = lambda v: getter(v.node)
        self.typecheckfuncs[name] = \
            lambda v: v.node.types.contains(nodeclass.get_type())

    def add_enum_type(self, name, fundytype, *values):
        py_to_fundy = {}
        fundy_to_py = {}
        for fundyval, pythonval in values:
            py_to_fundy[pythonval] = fundyval.node
            fundy_to_py[fundyval] = pythonval
        self.boxfuncs[name] = lambda v: py_to_fundy[v]
        self.extractfuncs[name] = lambda v: fundy_to_py[v]
        self.typecheckfuncs[name] = lambda v: v.node.types.contains(fundytype)

    def get_box_func(self, name):
        return self.boxfuncs[name]

    def get_extract_func(self, name):
        return self.extractfuncs[name]

    def get_typecheck_func(self, name):
        return self.typecheckfuncs[name]

_type_info = TypeTable()
_type_info.add_simple_type('int', IntNode)
_type_info.add_simple_type('char', CharNode)
_type_info.add_simple_type('string', StringNode)
_type_info.add_enum_type('unit', unit_type, (unit, None))
_type_info.add_enum_type('bool', bool_type,
                         (bool_true, True), (bool_false, False))



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

            box = _type_info.get_box_func(ret_type)

            # note: annoying _ names are to avoid making the outer variables
            # inherited from OpTable.op be interpreted as locals by assigning
            # to them
            if name is None:
                _name = func.func_name
            else:
                _name = name

            if num_params == 1:
                argcheck = _type_info.get_typecheck_func(_arg_types[0])
                extract = _type_info.get_extract_func(_arg_types[0])

                def wrapper(x):
                    if argcheck(x):
                        raw_ret = func(extract(x))
                        ret = box(raw_ret)
                        return ret
                    else:
                        raise TypeError     # TODO: proper exception here
                # end def wrapper

                wrapper.func_name = _name
                ptr = NodePtr(UnaryBuiltinNode(wrapper))
                if fixity is None:
                    _fixity = FIXITY.PREFIX

            elif num_params == 2:
                argcheck1, argcheck2 = map(_type_info.get_typecheck_func,
                                           _arg_types)
                extract1, extract2 = map(_type_info.get_extract_func,
                                         _arg_types)

                def wrapper(arg1, arg2):
                    if argcheck1(arg1) and argcheck2(arg2):
                        raw_ret = func(extract1(arg1), extract2(arg2))
                        ret = box(raw_ret)
                        return ret
                    else:
                        raise TypeError     # TODO: proper exception here
                # end def wrapper

                wrapper.func_name = _name
                ptr = NodePtr(BinaryBuiltinNode(wrapper))
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

            self.register_name(_name, ptr, _assoc, _prec, _fixity)

            return ptr
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

@ops.op(name='+', arg_types='int', prec=1000)
def plus(x, y):
    return x + y

@ops.op(name='-', arg_types='int', prec=1000)
def plus(x, y):
    return x - y

@ops.op(name='*', arg_types='int', prec=2000)
def plus(x, y):
    return x * y

@ops.op(name='/', arg_types='int', prec=2000)
def plus(x, y):
    return x // y

@ops.op(arg_types='int', prec=3000)
def neg(x):
    return -1 * x

@ops.op(name='and', arg_types='bool', prec=500)
def bool_and(x, y):
    return x and y

@ops.op(name='or', arg_types='bool', prec=500)
def bool_or(x, y):
    return x or y


pyops_context = ops.make_context()
