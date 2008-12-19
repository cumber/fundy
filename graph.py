
from pypy.lang.fundy.utils import Enum


# define type code enums
TYPE = Enum('INTEGER', 'STRING', 'CHAR')


class W_Value(object):
    """
    Represents a runtime app-level value
    """
    pass

class W_Int(object):
    """
    Represents a runtime app-level int
    """
    def __init__(self, value):
        self.type_info = TYPE.INTEGER
        self.intval = value

    def to_string(self):
        return str(self.intval)

    to_repr = to_string

class W_String(object):
    """
    Represents a runtime app-level string
    """
    def __init__(self, value):
        self.type_info = TYPE.STRING
        self.strval = value

    def to_string(self):
        return self.strval

    def to_repr(self):
        return repr(self.str_value)

class W_Char(W_String):
    """
    Represents a runtime app-level character
    """
    def __init__(self, value):
        assert len(value) == 1
        W_String.__init__(self, value)
        self.type_info = CHAR


class ReductionError(Exception):
    """
    An error encountered during reduction
    """
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        if self.message is not None:
            return "ReductionError: " + self.message
        else:
            return "ReductionError"


# constants for the Node tags
TAG = Enum('VALUE', 'BUILTIN', 'LAMBDA', 'APPLICATION')

# constants for associativity
ASSOC = Enum('LEFT', 'RIGHT', 'NONE')

class Node(object):
    def __init__(self, tag, functor=None, argument=None, body=None,
                 value=None, type_info=None, code=None,
                 assoc=ASSOC.NONE, prec=0, num_params=None, args=[]):
        self.tag = tag
        self.functor = functor
        self.argument = argument
        self.body = body
        self.value = value
        self.type_info = type_info
        self.code = code
        self.assoc = assoc
        self.prec = prec
        self.num_params = num_params
        self.args = args

    def __repr__(self, seen_lambdas=[]):
        if self.tag is TAG.VALUE:
            return '%s %s' % (self.tag, self.value.to_repr())
        elif self.tag is TAG.BUILTIN:
            return '%s %s (%s, %d, %d, %s)' % (self.tag, self.code.func_name,
                                               self.assoc, self.prec,
                                               self.num_params, self.args)
        elif self.tag is TAG.LAMBDA:
            try:
                x = seen_lambdas.index(self)
                return 'v%d' % x
            except ValueError:
                seen_lambdas = seen_lambdas + [self]
                return '%s v%d: (%s)' % (self.tag, len(seen_lambdas) - 1,
                                         self.body.__repr__(seen_lambdas))
        elif self.tag is TAG.APPLICATION:
            return '%s(%s, %s)' % (self.tag,
                                   self.functor.__repr__(seen_lambdas),
                                   self.argument.__repr__(seen_lambdas))

    def overwrite(self, other):
        self.tag = other.tag
        self.functor = other.functor
        self.argument = other.argument
        self.body = other.body
        self.value = other.value
        self.type_info = other.type_info
        self.code = other.code
        self.assoc = other.assoc
        self.prec = other.prec
        self.num_params = other.num_params
        self.args = other.args

    def copy(self):
        new = Node(tag=self.tag)
        new.overwrite(self)
        return new

    def is_operator(self):
        return not self.assoc is ASSOC.NONE

    def reduce_WHNF(self):
        if self.tag is TAG.APPLICATION:           
            self.functor.reduce_WHNF()
            # self.functor should now be a lambda node or a builtin node
            if self.functor.tag is TAG.LAMBDA:
                new_graph = self.functor.body.instantiate([(self.functor,
                                                            self.argument)])
                self.overwrite(new_graph)
            elif self.functor.tag is TAG.BUILTIN:
                if self.functor.num_params == 1:    # last arg, can call
                    args = self.functor.args
                    args.append(self.argument)
                    for n in args:
                        n.reduce_full()
                    self.overwrite(self.functor.code(*args))
                elif self.functor.num_params > 1:   # still need more arguments
                    new = Node(tag=TAG.BUILTIN, code=self.functor.code,
                               assoc=self.functor.assoc, prec=self.functor.prec,
                               num_params=(self.functor.num_params - 1),
                               args=(self.functor.args + [self.argument]))
                    self.overwrite(new)
                else:
                    assert False
            else:
                assert False
            self.reduce_WHNF()
        # end if self.tag is TAG.APPLICATION
    # end def reduce_WHNF
                    

    def reduce_full(self):
        self.reduce_WHNF()
        for n in [self.functor, self.argument, self.body]:
            if n is not None:
                n.reduce_full()

    def instantiate(self, substitutions):
        """
        Constructs a new instance of the graph starting at this node, making
        replacements. substitutions is a list of pairs: if any node in the graph
        being copied contains a reference to one of the first elements in
        substitutions, it is replaced by a reference to the corresponding
        second element.
        """
        for old, new in substitutions:
            if self is old:
                return new

        if self.tag is TAG.APPLICATION:
            # new application, instantiating the functor and argument
            new_func = self.functor.instantiate(substitutions)
            new_arg = self.argument.instantiate(substitutions)
            if new_func is self.functor and new_arg is self.argument:
                # if both children turned out to not need copying, we don't
                # need to make a new application node
                return self
            else:
                return Application(new_func, new_arg)
        
        elif self.tag is TAG.LAMBDA:
            # new lambda, but as a lambda's parameter is represented by a
            # loopback reference to the lambda node itself, we need to add
            # to our list of substitutions to replace references to the old
            # lambda node with references to the newly constructed lambda node
            new_lambda = Node(tag=TAG.LAMBDA)
            new_subs = substitutions + [(self, new_lambda)]
            new_lambda.body = self.body.instantiate(new_subs)
            return new_lambda

        else:
            # no need to copy
            return self

            


def Application(functor, argument):
    """
    Helper function to make APPLICATION nodes
    """
    return Node(tag=TAG.APPLICATION, functor=functor, argument=argument)

def Lambda():
    """
    Helper function to make LAMBDA nodes; has no body, since references in the
    body to the lambda's formal parameter are represented by backreferences to
    the lambda node, so the body must usually be generated after the lambda
    node and then attached.
    """
    return Node(tag=TAG.LAMBDA)

def Value(intval=None, strval=None, wrapped_value=None):
    """
    Helper function to make VALUE nodes 
    """
    if wrapped_value is not None:
        pass
    elif intval is not None:
        wrapped_value = W_Int(intval)
    elif strval is not None:
        wrapped_value = W_String(strval)
    return Node(tag=TAG.VALUE, value=wrapped_value)

def Builtin(code, assoc=None, prec=None):
    """
    NOT_RPYTHON: Helper function to make BUILTIN nodes
    """
    return Node(tag=TAG.BUILTIN, code=code, assoc=assoc, prec=prec,
                num_params=code.func_code.co_argcount)
