
from graph import NodePtr, PrimitiveNode, LabelledValue
from utils import rset
from context import Context, OperatorRecord


default_context = Context()

#---------------------------#
# builtin type objects      #
#---------------------------#

# type is a weird object; it is its own type
_type = LabelledValue('type')
_type.add_type(_type)
default_context.bind('type', _type)

def _make_primitive_type(name):
    tmp = LabelledValue(name)
    tmp.add_type(_type)
    default_context.bind(name, tmp)
    return tmp

def _make_primitive_types(*names):
    return map(_make_primitive_type, names)

int_type, char_type, str_type = _make_primitive_types('int', 'char', 'string')

# The unit and bool types are special; instances of them are not constructed
# at runtime, they already exist.
def _make_enum_type(overall_type_name, *constructor_names):
    overall_type = _make_primitive_type(overall_type_name)
    constructors = _make_primitive_types(*constructor_names)
    for c in constructors:
        c.add_type(overall_type)
    return [overall_type] + constructors

unit_type, unit = _make_enum_type('unittype', 'unit')
bool_type, bool_false, bool_true = _make_enum_type('bool', 'false', 'true')


class IntNode(PrimitiveNode):
    def __init__(self, value):
        PrimitiveNode.__init__(self)
        self.types.add(int_type)
        self.intval = value

    def to_string(self):
        return str(self.intval)

    def get_int(self):
        return self.intval

    @staticmethod
    def get_type():
        return int_type

    @staticmethod
    def make_getter():
        """
        NOT_RPYTHON:
        """
        return lambda i: getattr(i, 'intval')

    to_repr = to_string

class CharNode(PrimitiveNode):
    def __init__(self, value):
        assert len(value) == 1
        PrimitiveNode.__init__(self)
        self.types.add(char_type)
        self.charval = value

    def to_string(self):
        return self.charval

    get_char = to_string

    @staticmethod
    def get_type():
        return char_type

    @staticmethod
    def make_getter():
        """
        NOT_RPYTHON:
        """
        return lambda c: getattr(c, 'charval')

    def to_repr(self):
        return repr(self.charval)

class StringNode(PrimitiveNode):
    def __init__(self, value):
        PrimitiveNode.__init__(self)
        self.types.add(str_type)
        self.strval = value

    def to_string(self):
        return self.strval

    get_string = to_string

    @staticmethod
    def get_type():
        return str_type

    @staticmethod
    def make_getter():
        """
        NOT_RPYTHON:
        """
        return lambda s: getattr(s, 'strval')

    def to_repr(self):
        return repr(self.strval)

def IntPtr(i):
    return NodePtr(IntNode(i))

def CharPtr(c):
    return NodePtr(CharNode(c))

def StrPtr(s):
    return NodePtr(StringNode(s))

def BoolPtr(b):
    if b:
        return bool_true
    else:
        return bool_false

def UnitPtr():
    return unit


from pyops import pyops_context
default_context.update(pyops_context)
