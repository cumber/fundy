
# Notes on the confusing pattern of returns when reducing/applying/instantiating
# cells and nodes:
# reducing a cell overwrites its node with the result of reducing that node
# reducing a node returns a node that is the result of applying its functor to
#        its argument (or itself if it's not an application node)
# applying cell1 to cell2 returns a node that is the result of applying cell1's
#        node to cell2
# applying a node to a cell returns a node that is the result of instantiating
#        its body, replacing its parameter with the cell
# instantiating a cell returns a node, that is the result of instantiating its
#        node
# instantiating a node returns a new copy of itself (recursively making new
#        cells to replace its child cells, or referencing the replacement cell
#        if one of its children is the cell to be replaced)

class Cell(object):
    """
    A cell contains a node of the graph. Its methods just forward to to the node
    it contains. The reason for this two-part representation is that when a node
    is reduced, we want to overwrite the node with the result of the reduction,
    so that other references in the graph now refer to the new node and the work
    does not have to be repeated. The node is not able to merely overwrite its
    own members, as it usually needs to change the subclass of node.
    """
    def __init__(self, node):
        self.node = node
    
    def reduce_WHNF(self):
        """
        Replaces the node inside this cell with the result of reducing that node
        to weak head normal form.
        """
        self.node = self.node.get_reduced_node_WHNF()
        
    def get_applied_node(self, argument):
        """
        Applies the node inside this cell to argument, returning a new node.
        """
        n = self.node
        if isinstance(n, BuiltinNode):
            return n.apply(argument)
        elif isinstance(n, LambdaNode):
            return n.apply(argument)
        else:
            raise TypeError
        
    
    def get_instantiated_node(self, replace_this, with_this):
        """
        Instantiates the node inside this cell, returning a new node. The graph
        under the new node is the result of copying the graph under the original
        this cell's node, but replacing all references to replace_this with
        references to with_this.
        replace_this and with_this are both cells, not nodes.
        """
        return self.node.instantiate(replace_this, with_this)

    def instantiate(self, replace_this, with_this):
        """
        Like get_instantiated_node, but returns a new Cell containing the node
        instead of returning the node directly. Convenience function for the
        deeper levels of instantiation that are creating new cells, as opposed
        to the top level of instantiation that is returning a node for a cell
        being reduced to overwrite its node with.
        """
        new_node = self.node.instantiate(replace_this, with_this)
        if new_node is self.node:
            # only need to make a new cell if the node has changed
            return self
        else:
            return Cell(self.node.instantiate(replace_this, with_this))

    #def kind(self):
    #    return type(self.node)
    
    #def is_operator(self):
    #    return self.node.is_operator()
    
    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        # toplevel is just to make sure that the repr for a Cell says that
        # it's a Cell, whereas the repr for a node doesn't, but only at
        # the top level, so the graph is easier to read
        if toplevel:
            return 'Cell(%s)' % self.node.__repr__(False)
        else:
            return self.node.__repr__(toplevel)


class Node(object):
    """
    Base class for the different kinds of node.
    """
    def get_reduced_node_WHNF(self):
        """
        Return a Node that is the result of reducing this Node to weak head
        normal form. Either returns a new Node, or self.
        """
        return self     # by default reduction doesn't change nodes
    
    def instantiate(self, replace_this_cell, with_this_cell):
        """
        Instantiates a node, returning a node that is the result of replacing
        one cell with another in the subgraph under this node. Returns self
        only in the case where it is absolutely known that replace_this_cell
        cannot occur in the subgraph under this node (basically  
        """
        raise NotImplementedError
    
    def apply(self, argument_cell):
        """
        Applies a node to an argument, returning a node that is the result of
        the application.
        """
        raise TypeError   # only lambdas and builtins can be applied
    
    #def is_operator(self):
    #    return False

    def to_string(self):
        raise NotImplementedError



class ApplicationNode(Node):
    def __init__(self, functor, argument):
        self.functor = functor
        self.argument = argument
        
    def get_reduced_node_WHNF(self):
        self.functor.reduce_WHNF()
        # self.functor should now be a lambda node or a builtin node
        new_node = self.functor.get_applied_node(self.argument)
        # now try to reduce the result, in case it returned another application
        return new_node.get_reduced_node_WHNF()
    
    def instantiate(self, replace_this_cell, with_this_cell):
        if replace_this_cell is self.functor:
            new_functor = with_this_cell
        else:
            new_functor = self.functor.instantiate(replace_this_cell,
                                                   with_this_cell)
        
        if replace_this_cell is self.argument:
            new_argument = with_this_cell
        else:
            new_argument = self.argument.instantiate(replace_this_cell,
                                                     with_this_cell)
         
        if new_functor is self.functor and new_argument is self.argument:
            # no need to create a new node if both the functor and the argument
            # ended up being the same
            return self
        else:
            return ApplicationNode(new_functor, new_argument)

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'Application(%s to %s)' % (self.functor.__repr__(toplevel),
                                          self.argument.__repr__(toplevel))
    

class LambdaNode(Node):
    def __init__(self, parameter, body):
        self.parameter = parameter
        self.body = body
    
    def apply(self, argument):
        if self.body is self.parameter:     # if the body is just the param
            return argument.node            # just return the arg node now
        return self.body.get_instantiated_node(self.parameter, argument)
    
    def instantiate(self, replace_this_cell, with_this_cell):
        assert replace_this_cell is not self.parameter, \
            "Don't instantiate a lambda replacing its parameter, apply it to something"
        
        if self.body is replace_this_cell:
            new_body = with_this_cell
        else:
            new_body = self.body.instantiate(replace_this_cell, with_this_cell)
        
        if new_body is self.body:
            # no need to create new node if the body didn't change
            return self
        else:
            return LambdaNode(self.parameter, new_body)

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'LAMBDA %s --> %s' % (self.parameter.__repr__(toplevel),
                                     self.body.__repr__(toplevel))


class BuiltinNode(Node):
    #def __init__(self, code, num_params, assoc, prec, arguments=[]):
    #    self.code = code
    #    self.assoc = assoc
    #    self.prec = prec
    #    self.args_needed = num_params
    #    self.arguments = arguments
    #    
    #def apply(self, argument):
    #    if self.args_needed == 1:
    #        # have enough arguments to apply the builtin, reduce them fully
    #        # to make sure they are value nodes
    #        arg_cells = self.arguments + [argument]
    #        arg_nodes = []
    #        for a in arg_cells:
    #            a.reduce_WHNF()
    #            arg_nodes.append(a.node)
    #        return self.code(*arg_nodes)
    #    elif self.args_needed > 1:
    #        return BuiltinNode(self.code, self.args_needed - 1, self.assoc,
    #                           self.prec, self.arguments + [argument])
    #    else:
    #        assert False 
    #
    #def instantiate(self, replace_this_cell, with_this_cell):
    #    new_args = []
    #    for a in self.arguments:
    #        new_args.append(a.instantiate(replace_this_cell, with_this_cell))
    #    return BuiltinNode(self.code, self.args_needed, self.assoc, self.prec,
    #                       self.arguments)
    
    #def is_operator(self):
    #    return self.assoc is not ASSOC.NONE
    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'BUILTIN %s' % self.func.func_name
            
class ParameterNode(Node):
    # used in __repr__ of ParameterNode, should not be needed by translation
    _param_dict = {}

    def __init__(self):
        pass    # parameter nodes don't actually hold any information other than
                # their identity
    
    def instantiate(self, replace_this_cell, with_this_cell):
        # parameters have no children, so do not need to make a copy as it will
        # always be identical to the original (and this simplifies instantiation
        # of lambda nodes, which assume they can just reuse the parameter node)
        return self

    def __repr__(self, toplevel=True):
        if not self in self._param_dict:
            self._param_dict[self] = 'v%d' % len(self._param_dict)
        return self._param_dict[self]



class ValueNode(Node):
    def instantiate(self, replace_this_cell, with_this_cell):
        return self

    def __repr__(self, toplevel=True):
        return 'VALUE %s' % self.to_string()

class StringNode(ValueNode):
    def __init__(self, value):
        self.strval = value
    
    def to_string(self):
        return self.strval
    
    get_string = to_string
    
    def to_repr(self):
        return repr(self.strval)

class CharNode(ValueNode):
    def __init__(self, value):
        assert len(value) == 1
        self.charval = value

    def to_string(self):
        return self.charval

    get_char = to_string

    def to_repr(self):
        return repr(self.strval)
    
class IntNode(ValueNode):
    def __init__(self, value):
        self.intval = value
    
    def to_string(self):
        return str(self.intval)

    def get_int(self):
        return self.intval
    
    to_repr = to_string



def Application(functor, argument):
    """
    Helper function to make cells containing application nodes
    """
    return Cell(ApplicationNode(functor, argument))

def Lambda(param, body):
    """
    Helper function to make cells containing lambda nodes
    """
    return Cell(LambdaNode(param, body))

def Param():
    """
    Helper function to make cells containing parameter nodes
    """
    return Cell(ParameterNode())

#def ValueNode(intval=None, strval=None, charval=None):
#    """
#    Helper function to make the appropriate ValueNode for a python value
#    """
#    if intval is not None:
#        return IntNode(intval)
#    elif strval is not None:
#        return StringNode(strval)
#    elif charval is not None:
#        return CharNode(charval)
#    else:
#        assert False

def CharCell(c):
    return Cell(CharNode(c))

def IntCell(i):
    return Cell(IntNode(i))

def StrCell(s):
    return Cell(StringNode(s))

def Builtin(code, assoc=None, prec=None):
    """
    NOT_RPYTHON: Helper function to make BUILTIN nodes
    """
    return Cell(BuiltinNode(code, code.func_code.co_argcount, assoc, prec))
