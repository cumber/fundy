
from pypy.lang.fundy.graph import Builtin, Value, W_Int, LEFT, RIGHT, NONE


default_context = {}



def builtin(name, assoc=NONE, prec=0):
    """
    NOT_RPYTHON: Decorator factory for adding function definitions
    """
    def decorator(func):
        func.func_name = name
        node = Builtin(code=func, assoc=assoc, prec=prec)
        default_context[name] = node
        return node
    return decorator


##@builtin('+', assoc=LEFT, prec=10)
##def add(v1, v2):
##    if isinstance(v1.value, W_Int) and isinstance(v2.value, W_Int):
##        return Value(intval=(v1.value.int_value + v2.value.int_value))
##
##@builtin('*', assoc=LEFT, prec=20)
##def mul(v1, v2):
##
##
##
##int_op('+', LEFT, 10, add)

def int_op(name, assoc, prec):
    def decorator(func):
        @builtin(name, assoc, prec)
        def int_operator(x, y):
            if isinstance(x.value, W_Int) and isinstance(y.value, W_Int):
                return Value(intval=func(x.value.int_value, y.value.int_value))
        return int_operator
    return decorator

@int_op('+', LEFT, 10)
def add(x, y):
    return x + y

@int_op('-', LEFT, 10)
def sub(x, y):
    return x - y

@int_op('*', LEFT, 20)
def mul(x, y):
    return x * y

@int_op('/', LEFT, 20)
def mul(x, y):
    return x / y


