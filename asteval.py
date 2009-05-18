
from pypy.rlib.parsing.tree import RPythonVisitor, Symbol, Nonterminal

import globals
from utils import dotview, LabelledGraph
from graph import Application, BuiltinNode, Lambda, Param, Cons, ConsNode
from builtin import default_context, IntPtr, CharPtr, StrPtr, unit
from pyops import ASSOC


def _visit_show_statement(self, node):
    """
    NOT_RPYTHON: Visually display the argument expressions as graphs.

    The show statement is for debugging/educational purposes, and the current
    implementation can only be used when running Fundy on top of CPython.
    Therefore this function is conditionally added as a method of the Eval
    class below, being excluded if we are setting up for low-level translation.
    """
    lgs = [LabelledGraph(self, astexpr=n) for n in node.children]
    if not lgs:
        # no arguments to show given; show entire context
        lgs = [LabelledGraph(self, graph=g, label=n)
               for (n, g) in self.context.items()]
    dotview(*lgs)

class Eval(RPythonVisitor):
    """
    Evaluates fundy code in the form of a parse tree (see parse.py). There are
    two kinds of vist_* method: statement-level methods that must return None
    but may update self.context (name binding), and expression-level methods
    that return a graph (see graph.py), and may not update self.context (but
    may refer to it for name resolution).
    """
    def __init__(self, context=default_context):
        """
        context is the initial context to use; dictionary mapping strings to
        graph nodes
        """
        self.context = context.copy()

    def visit_program(self, node):
        for n in node.children:
            self.dispatch(n)

    def visit_print_statement(self, node):
        for n in node.children:
            graph = self.dispatch(n)
            graph.reduce_WHNF_inplace()
            # graph should now be a value node
            print graph.node.to_string()

    if not globals.setup_for_translation:
        visit_show_statement = _visit_show_statement


    def visit_assign_statement(self, node):
        ident = node.children[0]
        block = node.children[-1]

        # This is slightly wacky: RPython can only use negative slices for the
        # special case x[:-1]. For both x[1:-1] and x[1:len(x)-1] the annotator
        # complains about not being able to prove the slice stop non-negative.
        params = node.children[:-1]
        params.pop(0)

        assert isinstance(ident, Symbol)
        name = ident.additional_info

        # create a scope for the function's parameters and local variables
        local_scope = Eval(self.context)

        # bind the name in the original scope
        self.context.bind(name, local_scope.make_lambda_chain(params, block))

    def make_lambda_chain(self, params, body):
        # Helper for visit_assign_statement. Dispatches each of params in order,
        # (binding names to Param nodes if they are param nonterminals as
        # expected), before dispatching the body (which will usually need the
        # names of the params to be bound). Returns chain of lambda nodes, each
        # containing the next as its body, with the body of the last being the
        # dispatched body passed in. Much easier to write this recursively than
        # using loops in-line in the body of visit_assign_statement.
        if params:
            param = self.dispatch(params[0])
            return Lambda(param, self.make_lambda_chain(params[1:], body))
        else:
            return self.dispatch(body)

    def visit_param(self, node):
        new_param = Param()
        ident = node.children[0]    # param has only one child
        assert isinstance(ident, Symbol)
        name = ident.additional_info
        self.context.bind(name, new_param)
        return new_param

    def visit_block(self, node):
        # last item is the expression to be returned, any other items
        # are name binding statements for the current context
        for i in xrange(len(node.children) - 1):
            self.dispatch(node.children[i])
        return self.dispatch(node.children[-1])

    def visit_type_statement(self, node):
        ident = node.children[0]
        assert isinstance(ident, Symbol)
        name = ident.additional_info

        # dispatch data constructors
        constructors = [self.dispatch(node.children[i])
                        for i in range(1, len(node.children))]

        # type object is then a cons tree of the alternatives
        type_node = ConsNode.make_tree(constructors)

        self.context.bind(name, type_node)

    def visit_constructor(self, node):
        ident = node.children[0]
        assert isinstance(ident, Symbol)
        name = ident.additional_info

        if len(node.children) == 1:
            # no-argument constructor, just bind it to unit
            constructor = unit
        else:
            # until record types are implemented, we don't actually care
            # about the names of the constructor arguments, only the number
            param_nodes = [Param() for i in range(1, len(node.children))]
            body = ConsNode.make_tree(param_nodes)

            # build the lambda nodes in reverse order, as each contains the next
            param_nodes.reverse()
            for param in param_nodes:
                body = Lambda(param, body)

            # now body is the top level lambda node
            constructor = body

        # now bind the name to the constructor
        self.context.bind(name, constructor)
        return constructor

    def visit_expr(self, node):
        graph_stack = []
        oper_stack = []

        for n in node.children:
            # function symbol
            if n.symbol == 'IDENT':
                assert isinstance(n, Symbol)
                n_graph = self.dispatch(n)
                name = n.additional_info
                if not self.context.is_operator(name):
                    graph_stack.append(n_graph)
                else:
                    n_assoc = self.context.get_assoc(name)
                    n_prec = self.context.get_prec(name)
                    n_fix = self.context.get_fixity(name)
                    while True:
                        if not oper_stack:
                            break;
                        o_graph, o_assoc, o_prec, o_fix = oper_stack[-1]
                        if (n_prec < o_prec or
                                (n_assoc is ASSOC.LEFT and n_prec == o_prec)
                            ):
                            # already have oper, but remove from stack
                            oper_stack.pop()
                            arg2 = graph_stack.pop()
                            arg1 = graph_stack.pop()
                            apply_to_arg1 = Application(o_graph, arg1)
                            apply_to_arg2 = Application(apply_to_arg1, arg2)
                            graph_stack.append(apply_to_arg2)
                        else:
                            break
                    oper_stack.append((n_graph, n_assoc, n_prec, n_fix))
            else:
                graph_stack.append(self.dispatch(n))

        # finished looking at the chain, give arguments to any operators
        # left on the operator stack
        while oper_stack:
            oper, _assoc, _prec, _fix = oper_stack.pop()
            arg2 = graph_stack.pop()
            arg1 = graph_stack.pop()
            apply_to_arg1 = Application(oper, arg1)
            apply_to_arg2 = Application(apply_to_arg1, arg2)
            graph_stack.append(apply_to_arg2)

        # now any expressions involving binary operators should have been
        # replaced by single graphs applying the operator to its arguments
        # the remaining chain is presumed to be function calls
        f = graph_stack[0]
        for i in xrange(1, len(graph_stack)):
            f = Application(functor=f, argument=graph_stack[i])
        return f
    # end def visit_expr

    def visit_IDENT(self, node):
        # lookup the identifier in the context and return its graph
        return self.context.lookup(node.additional_info)

    def visit_NUMBER(self, node):
        return IntPtr(int(node.additional_info))

    def visit_STRING(self, node):
        string = node.additional_info.strip('"')
        return StrPtr(string)

    def visit_CHAR(self, node):
        char = node.additional_info.strip("'")
        assert len(char) == 1
        return CharPtr(char)
