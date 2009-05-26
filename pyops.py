"""
This module defines builtin Fundy functions that are defined using Python code.
"""

from graph import BuiltinNode, PrimitiveNode, ConsNode, NodePtr
from utils import Enum, dot_node, dot_link
from builtin import IntNode, CharNode, StringNode, unit_type, unit, \
                    bool_type, bool_false, bool_true

ASSOC = Enum('LEFT', 'RIGHT', 'NONE')
FIXITY = Enum('PREFIX', 'INFIX', 'POSTFIX')

from context import Context, OperatorRecord, SimpleRecord


class N_aryBuiltinMeta(type):
    def __new__(metacls, classname, bases, dic):
        """
        NOT_RPYTHON:
        """
        argnames = ['arg%d' % i for i in range(dic['N'])]

        frags = []
        arg_defaults = ', '.join(['%s=None' % name for name in argnames])
        frags.append('def __init__(self, func, %s):' % arg_defaults)
        frags.append('    BuiltinNode.__init__(self)')
        frags.append('    self.func = func')
        for name in argnames:
            frags.append('    self.%s = %s' % (name, name))
        exec '\n'.join(frags)
        dic['__init__'] = __init__

        frags = []
        frags.append('def apply(self, argument):')
        frags.append('    applied = False')
        for name in argnames:
            frags.append('    if not applied and not self.%s:' % name)
            frags.append('        %s = argument' % name)
            frags.append('        applied = True')
            frags.append('    else:')
            frags.append('        %s = self.%s' % (name, name))
        frags.append('    assert applied')

        not_nones = ' and '.join(argnames)
        frags.append('    if %s:' % not_nones)    # can apply func
        for name in argnames:
            frags.append('        %s.reduce_WHNF_inplace()' % name)
        args = ', '.join(argnames)
        frags.append('        return self.func(%s)' % args)
        frags.append('    else:')
        frags.append('        return %s(self.func, %s)' % (classname,
                                                                     args))
        exec '\n'.join(frags)
        dic['apply'] = apply

        frags = []
        frags.append('def instantiate(self, replace_this_ptr, with_this_ptr):')
        frags.append('    nochange = True')
        for name in argnames:
            frags.append('    if self.%s:' % name)
            frags.append('        %s = self.%s.get_instantiated_node_ptr('
                           'replace_this_ptr, with_this_ptr)' % (name, name))
            frags.append('        nochange = %s is self.%s' % (name, name))
            frags.append('    else:')
            frags.append('        %s = None' % name)

        frags.append('    if nochange:')
        frags.append('        return self') # no need to make a new copy
        frags.append('    else:')
        frags.append('        return %s(self.func, %s)' % (classname, args))
        exec '\n'.join(frags)
        dic['instantiate'] = instantiate

        dic['get_name'] = lambda self: self.func.func_name
        cls = type(classname, bases, dic)

        arg_links = {}
        for name in argnames:
            arg_links[name] = dict(color='blue', style='dotted', label=name)
        cls.add_dot_fn(dict(shape='ellipse', color='green',
                            label=lambda self: self.func.func_name),
                       **arg_links)

        return cls

class UnaryBuiltinNode(BuiltinNode):
    __metaclass__ = N_aryBuiltinMeta
    N = 1

class BinaryBuiltinNode(BuiltinNode):
    __metaclass__ = N_aryBuiltinMeta
    N = 2

class TernaryBuiltinNode(BuiltinNode):
    __metaclass__ = N_aryBuiltinMeta
    N = 3

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
_type_info.add_enum_type('unit', unit_type, (unit, 0))
_type_info.add_enum_type('bool', bool_type,
                         (bool_true, True), (bool_false, False))



class OpTable(object):
    """
    NOT_RPYTHON:
    """

    # TODO: this class is now being used more as a "primitive function definer"
    # than as an operator table. Should at least rename it. Probably needs some
    # refactoring as well, to make more of its functionality reuseable.
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

            if fixity is None and assoc is None and prec is None:
                self.register_func(_name, ptr)
            else:
                self.register_op(_name, ptr, _assoc, _prec, _fixity)

            return ptr
        # end def decorator

        return decorator
    # end def OpTable.op

    def func(self, name=None, arg_types=None, ret_type=None):
        """
        NOT_RPYTHON: Defines a primitive function rather than an operator.
        """
        return self.op(name, arg_types, ret_type, None, None, None)

    def register_func(self, name, graph):
        record = SimpleRecord(graph)
        if not name in self._db:
            self._db[name] = set()
        self._db[name].add(record)

    def register_op(self, name, graph, assoc, prec, fixity):
        record = OperatorRecord(graph, assoc, prec, fixity)
        if not name in self._db:
            self._db[name] = set()
        self._db[name].add(record)

    def make_context(self):
        c = Context()
        for name, recordset in self._db.items():
            for r in recordset:
                if hasattr(r, 'fixity'):
                    c.bind_operator(name, r.graph, r.assoc, r.prec, r.fixity)
                else:
                    c.bind(name, r.graph)
        return c


ops = OpTable()

@ops.op(name='+', arg_types='int', prec=1000)
def plus(x, y):
    return x + y

@ops.op(name='-', arg_types='int', prec=1000)
def minus(x, y):
    return x - y

@ops.op(name='*', arg_types='int', prec=2000)
def mul(x, y):
    return x * y

@ops.op(name='/', arg_types='int', prec=2000)
def div(x, y):
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


# Define the context!
pyops_context = ops.make_context()


# Following some handcrafted functions are written. These need to take graph
# pointers as arguments, and so cannot be automatically wrapped like the
# builtin in operations above.

def eq(left, right):
    if left.node is right.node:
        return True

    left.reduce_WHNF_inplace()
    right.reduce_WHNF_inplace()

    if not isinstance(right.node, type(left.node)):
        raise TypeError("cannot compare values of different types for equality")

    if isinstance(left.node, PrimitiveNode):
        return left.node.eq(right.node)
    elif isinstance(left.node, ConsNode):
        return eq(left.node.a, right.node.a) and eq(left.node.b, right.node.b)
    else:
        raise TypeError("Can't compare non-value types for equality")

_box_bool = _type_info.get_box_func('bool')
def boxed_eq(left, right):
    return _box_bool(eq(left, right))
boxed_eq.func_name = '=='

eq_ptr = NodePtr(BinaryBuiltinNode(boxed_eq))
pyops_context.bind_operator('==', eq_ptr, ASSOC.LEFT, 250, FIXITY.INFIX)


def if_then_else(cond, then_part, else_part):
    if eq(cond, bool_true):
        return then_part.node
    else:
        return else_part.node

if_then_else.func_name = 'if'

if_ptr = NodePtr(TernaryBuiltinNode(if_then_else))
pyops_context.bind('if', if_ptr)
