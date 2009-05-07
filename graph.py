
class NodePtr(object):
    """
    A NodePtr is a reference to a node.

    It can be dynamically reassigned. All other objects that want to refer to a
    node should do it through a NodePtr, allowing the reference to be
    over-written in place to point to a new node. Otherwise, this would be
    possible in Python, but not in RPython as it is not possible to change the
    __class__ to a different subclass of Node.

    The primary reason for this explicit indirection is that reduction of a node
    should be able to replace the original node with its reduction in-place, or
    other references to the same node would have to reduce it again.
    """
    def __init__(self, node):
        self.node = node

    def reduce_WHNF_inplace(self):
        """
        Replace the pointed at node with the result of reducing that node
        to weak head normal form.
        """
        self.node = self.node.reduce_WHNF()

    def get_applied_node(self, argument_ptr):
        """
        Apply the pointed at node to argument, returning a new node.
        """
        n = self.node
        if isinstance(n, BuiltinNode):
            return n.apply(argument_ptr)
        elif isinstance(n, LambdaNode):
            return n.apply(argument_ptr)
        else:
            raise TypeError


    def get_instantiated_node(self, replace_this_ptr, with_this_ptr):
        """
        Instantiate the node inside this ptr, returning a new node. The graph
        under the new node is the result of copying the graph under the original
        ptr's node, but replacing all references to replace_this with
        references to with_this.
        replace_this and with_this are both node pointers, not nodes.
        """
        return self.node.instantiate(replace_this_ptr, with_this_ptr)

    def get_instantiated_node_ptr(self, replace_this_ptr, with_this_ptr):
        """
        Like get_instantiated_node, but return a new NodePtr pointing to the
        node instead of returning the node directly. Convenience function for
        the deeper levels of instantiation that are creating new pointers to new
        nodes, as opposed to the top level of instantiation that is returning a
        node for a pointer being reduced to overwrite its node with.
        """
        new_node = self.node.instantiate(replace_this_ptr, with_this_ptr)
        if new_node is self.node:
            # shouldn't make a new pointer to the same node
            return self
        else:
            return NodePtr(new_node)

    #def kind(self):
    #    return type(self.node)

    #def is_operator(self):
    #    return self.node.is_operator()

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        # toplevel is just to make sure that the repr for a NodePtr says that
        # it's a NodePtr, whereas the repr for a node doesn't, but only at
        # the top level, so the graph is easier to read
        if toplevel:
            return '*(%s)' % self.node.__repr__(False)
        else:
            return self.node.__repr__(toplevel)


class Node(object):
    """
    Base class for the different kinds of node.

    The methods here do not modify the nodes, they return new nodes.

    Nodes should have NodePtr data members, not refer directly to other Nodes.
    """
    def reduce_WHNF(self):
        """
        Return a Node that is the result of reducing this Node to weak head
        normal form. Either returns a new Node, or self.
        """
        return self     # by default reduction doesn't change nodes

    def instantiate(self, replace_this_ptr, with_this_ptr):
        """
        Instantiate a node, returning a node that is the result of replacing
        one ptr with another in the subgraph under this node. Returns self
        only in the case where it is absolutely known that replace_this_ptr
        cannot occur in the subgraph under this node (basically at leaf nodes).
        """
        raise NotImplementedError

    def apply(self, argument_ptr):
        """
        Apply a node to an argument, returning a node that is the result of
        the application.
        """
        raise TypeError   # only lambdas and builtins can be applied

    #def is_operator(self):
    #    return False

    def to_string(self):
        raise NotImplementedError

    @classmethod
    def add_instantiate_fn(cls, *attr_names):
        """
        NOT_RPYTHON: Return an instantiation function.

        This is to define the common instantiation pattern in one place:

            for each attr:
                if attr is the thing to replace, replace it
                else replace attr with its own instantiation
            if all replacement attrs are the same as the original, return self
            else return new node created with the replacement attrs

        This function is not RPython, but the function it returns must be,
        which is why it is defined by eval()ing a string instead of using the
        perfectly adequate capabilities of Python.

        Manually defining an instantiation function that does this logic can
        be replaced by:

        class FOO:
            ...
        FOO.add_instantiate_fn(attr1, attr2, ..., attrN)

        attr1, attr2, ..., attrN must all be the names of data members of FOO
        nodes, and must all be of type NodePtr. Constructing a valid FOO must
        also be able to be acomplished by FOO(attr1, attr2, ..., attrN) (i.e.
        in the same order as the attributes appeared in the call to
        add_instantiate_fn).
        """
        conj_fragments = []
        arg_fragments = []
        func_fragments = ["def instantiate(self, replace_this_ptr, "
                                           "with_this_ptr):\n"]
        for name in attr_names:
            s = ("    if self.%(name)s is replace_this_ptr:\n"
                 "        new_%(name)s = with_this_ptr\n"
                 "    else:\n"
                 "        new_%(name)s = self.%(name)s."
                                    "get_instantiated_node_ptr("
                                        "replace_this_ptr, with_this_ptr)\n"
                ) % {'name': name}
            func_fragments.append(s)
            conj_fragments.append("new_%(name)s is self.%(name)s" %
                                        {'name': name})
            arg_fragments.append("new_%(name)s" % {'name': name})

        func_fragments += ["    if ", ' and '.join(conj_fragments), ":\n"
                           "        return self\n"
                           "    else:\n"
                           "        return ", cls.__name__, "(",
                                        ', '.join(arg_fragments), ")\n"]

        func_str = ''.join(func_fragments)
        exec func_str
        cls.instantiate = instantiate



class ApplicationNode(Node):
    def __init__(self, functor, argument):
        self.functor = functor
        self.argument = argument

    def reduce_WHNF(self):
        self.functor.reduce_WHNF_inplace()
        # self.functor should now be a lambda node or a builtin node
        new_node = self.functor.get_applied_node(self.argument)
        # now try to reduce the result, in case it returned another application
        return new_node.reduce_WHNF()

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'Application(%s to %s)' % (self.functor.__repr__(False),
                                          self.argument.__repr__(False))

ApplicationNode.add_instantiate_fn('functor', 'argument')


class LambdaNode(Node):
    def __init__(self, parameter, body):
        self.parameter = parameter
        self.body = body

    def apply(self, argument):
        if self.body is self.parameter:     # if the body is just the param
            return argument.node            # just return the arg node now
        return self.body.get_instantiated_node(self.parameter, argument)

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'LAMBDA %s --> %s' % (self.parameter.__repr__(False),
                                     self.body.__repr__(False))

LambdaNode.add_instantiate_fn('parameter', 'body')
LambdaNode.inner_instantiate = LambdaNode.instantiate
def outer_instantiate(self, replace_this_ptr, with_this_ptr):
    assert replace_this_ptr is not self.parameter, \
    "Don't instantiate a lambda replacing its parameter, apply it to something"
    return self.inner_instantiate(replace_this_ptr, with_this_ptr)
LambdaNode.instantiate = outer_instantiate


class BuiltinNode(Node):
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

    def instantiate(self, replace_this_ptr, with_this_ptr):
        # parameters have no children, so do not need to make a copy as it will
        # always be identical to the original (and this simplifies instantiation
        # of lambda nodes, which assume they can just reuse the parameter node)
        return self

    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        if not self in self._param_dict:
            self._param_dict[self] = 'v%d' % len(self._param_dict)
        return self._param_dict[self]



class ValueNode(Node):
    """
    Base class for nodes containing values.
    """
    pass


class ConsNode(ValueNode):
    """
    Cons node contains two other nodes. (pointers!)
    """
    def __init__(self, a, b):
        self.a = a
        self.b = b

ConsNode.add_instantiate_fn('a', 'b')


class PrimitiveNode(ValueNode):
    def instantiate(self, replace_this_ptr, with_this_ptr):
        return self

    def __repr__(self, toplevel=True):
        return 'VALUE %s' % self.to_string()

class StringNode(PrimitiveNode):
    def __init__(self, value):
        self.strval = value

    def to_string(self):
        return self.strval

    get_string = to_string

    def to_repr(self):
        return repr(self.strval)

class CharNode(PrimitiveNode):
    def __init__(self, value):
        assert len(value) == 1
        self.charval = value

    def to_string(self):
        return self.charval

    get_char = to_string

    def to_repr(self):
        return repr(self.strval)

class IntNode(PrimitiveNode):
    def __init__(self, value):
        self.intval = value

    def to_string(self):
        return str(self.intval)

    def get_int(self):
        return self.intval

    to_repr = to_string



def Application(functor, argument):
    """
    Helper function to make pointers to new application nodes
    """
    return NodePtr(ApplicationNode(functor, argument))

def Lambda(param, body):
    """
    Helper function to make pointers to new lambda nodes
    """
    return NodePtr(LambdaNode(param, body))

def Param():
    """
    Helper function to make pointers to new parameter nodes
    """
    return NodePtr(ParameterNode())

def Cons(a, b):
    """
    Helper funciton to make pointers to new cons nodes
    """
    return NodePtr(ConsNode(a, b))


def CharPtr(c):
    return NodePtr(CharNode(c))

def IntPtr(i):
    return NodePtr(IntNode(i))

def StrPtr(s):
    return NodePtr(StringNode(s))
