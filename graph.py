
from utils import dot_node, dot_link

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

    def nodeid(self):
        """
        Return a unique identifier for the node pointed at.
        """
        return self.node.nodeid()

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

    def dot(self):
        """
        NOT_RPYTHON: Yield dot format description of the graph under this node.

        Forwards to the node object itself. Will yield each graph element
        separately.
        """
        for dot in self.node.dot():
            yield dot


class Node(object):
    """
    Base class for the different kinds of node.

    The methods here do not modify the nodes, they return new nodes.

    Nodes should have NodePtr data members, not refer directly to other Nodes.
    """
    def nodeid(self):
        """
        Return a unique identifier for this node.
        """
        return id(self)

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

    def to_string(self):
        raise NotImplementedError

    def repr(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return "NODE_WITHOUT_REPR"

    def dot(self):
        """
        NOT_RPYTHON: Yield a description of the graph under this node.
        """
        yield dot_node(self.nodeid(), shape='ellipse',
                       label='UNRENDERABLE', color='red')

    @classmethod
    def add_instantiate_fn(cls, *attr_names):
        """
        NOT_RPYTHON: Add an instantiation function to the class.

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
    # end def add_instantiate_fn

    @classmethod
    def add_dot_fn(cls, self_spec, **attrs):
        """
        NOT_RPYTHON: Add a dot method to the class.

        This is to define the common dot render pattern in one place:

            yield render of self as a node (with various parameters)
            for each attr:
                yield render of link to attr (with various parameters)
                yield whatever attr.dot() yields

        self_spec should be a dictionary of parameters for the graph node to be
        rendered for nodes of this class: color (note US spelling!), shape, etc.

        Each extra keyword argument should be the name of an attribute that
        holds a NodePtr. Its value should be a dictionary of parameters for the
        link to be rendered.

        Manually defining a dot function that does this logic can be replaced
        by:

        class FOO:
            ...
        FOO.add_dot_fn(dict(...), attr2=dict(...), ..., attrN=dict(...))

        This function is not RPython, and the methods it creates do not have to
        be RPython at the moment either, as actually viewing the dot files that
        can be generated by these methods depends on PyGame, which is obviously
        not RPython, and so is only available when running on top of CPython.
        """
        # Compare with the hackery in add_instantiate_fn above;
        # this sort of thing is so much easier in Python than RPython.
        # Will be a pain to convert this if graph viewing is ever supported at
        # runtime in the translated interpreter.
        def dot(self):
            """
            NOT_RPYTHON: autogenerated dot method for class %s
            """ % cls.__name__
            yield dot_node(self.nodeid(), **self_spec)

            for attr_name, link_spec in attrs.items():
                attr_val = getattr(self, attr_name)
                yield dot_link(self.nodeid(), attr_val.nodeid(), **link_spec)
                for thing in attr_val.dot():
                    yield thing

        cls.dot = dot
    # end def add_dot_fn
# end class Node


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
ApplicationNode.add_dot_fn(dict(shape='ellipse', label='apply'),
                           functor=dict(color='blue', label='f'),
                           argument=dict(color='green', label='a'))

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

# small amount of hackery here; add the instantiate function then replace it
# with a wrapper around itself, so we can assert that the parameter is not the
# substitution of the instantiation. That would be very strange, as we normally
# apply a lambda to an argument by instantiating the body, replacing the
# parameter in the BODY with the argument. The parameter of a lambda node should
# never be anything other than a parameter node. (It shouldn't really even be
# a node, as it is rather a placeholder for one, but it needs to be unique for
# each lambda, and needs to be type-compatible with a node, so...)
LambdaNode.add_instantiate_fn('parameter', 'body')
LambdaNode.inner_instantiate = LambdaNode.instantiate
def outer_instantiate(self, replace_this_ptr, with_this_ptr):
    assert replace_this_ptr is not self.parameter, \
    "Don't instantiate a lambda replacing its parameter, apply it to something"
    return self.inner_instantiate(replace_this_ptr, with_this_ptr)
LambdaNode.instantiate = outer_instantiate

LambdaNode.add_dot_fn(dict(shape='octagon', label='lambda'),
                      parameter=dict(color='yellow', label='p'),
                      body=dict(color='red'))


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

ParameterNode.add_dot_fn(dict(shape='octagon', label='param', color='blue'))


class BuiltinNode(Node):
    def __repr__(self, toplevel=True):
        """
        NOT_RPYTHON:
        """
        return 'BUILTIN %s' % self.func.func_name

    def dot(self):
        """
        NOT_RPYTHON:
        """
        # NOTE: here we depend on all descendent classes of BuiltinNode
        # having a func member (which we could not do in RPython, unless they
        # all had the same type). But this is Python, so we can just override
        # this method anywhere the assumption doesn't hold.
        yield dot_node(self.nodeid(), shape='ellipse', color='yellow',
                       label=self.func.func_name)


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
ConsNode.add_dot_fn(dict(shape='box', label='cons'),
                    a=dict(label='a'),
                    b=dict(label='b'))


class PrimitiveNode(ValueNode):
    def instantiate(self, replace_this_ptr, with_this_ptr):
        return self

    def __repr__(self, toplevel=True):
        return 'VALUE %s' % self.to_repr()

    def dot(self):
        """
        NOT_RPYTHON: Yield a dot format description of a value node.

        This dot method is manually written rather than autogenerated because
        the label of the node should contain the value, rather than being
        statically determined by the class.
        """
        yield dot_node(self.nodeid(), shape='box', label=self.to_string())

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


def CharPtr(c):
    return NodePtr(CharNode(c))

def IntPtr(i):
    return NodePtr(IntNode(i))

def StrPtr(s):
    return NodePtr(StringNode(s))
