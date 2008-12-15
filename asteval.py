
from pypy.rlib.parsing.tree import RPythonVisitor
from pypy.lang.fundy.graph import Value, Application, LEFT
from pypy.lang.fundy.builtin import default_context

LEFT = 0
RIGHT = 1

class Eval(RPythonVisitor):
    """
    The visit_XXX methods of this class do not return anything, they modify
    self.context to reflect new bindings they encounter. ExprEval is used
    to evaluate expressions into graph structures.
    """
    def __init__(self, context=None):
        """
        context is the initial context to use; dictionary mapping strings to
        graph nodes
        """
        if context is None:
            self.context = default_context.copy()
        else:
            self.context = context
        
    def general_nonterminal_visit(self, node):
        print node
        for n in node.children:
            self.dispatch(n)

    def general_visit(self, node):
        print node

    def visit_program(self, node):
        for n in node.children:
            self.dispatch(n)

    def visit_print_statement(self, node):
        for n in node.children:
            graph = self.dispatch(n)
            graph.reduce_full()
            # graph should now be a value node
            print graph.value.to_string()
        
    def visit_expr(self, node):
        graph_stack = []
        oper_stack = []

        for n in node.children:
            # function symbol
            if n.symbol == 'IDENT':
                functor = self.dispatch(n)
                if not functor.is_operator():
                    graph_stack.append(functor)
                else:
                    while True:
                        if not oper_stack:
                            break;
                        oper = oper_stack[-1]
                        if (functor.prec < oper.prec or
                                (functor.assoc is LEFT and
                                 functor.prec == oper.prec)
                            ):
                            # already have oper, but remove from stack
                            oper_stack.pop()
                            arg2 = graph_stack.pop()
                            arg1 = graph_stack.pop()
                            apply_to_arg1 = Application(oper, arg1)
                            apply_to_arg2 = Application(apply_to_arg1, arg2)
                            graph_stack.append(apply_to_arg2)
                        else:
                            break
                    oper_stack.append(functor)
            else:
                graph_stack.append(self.dispatch(n))

        # finished looking at the chain, give arguments to any operators
        # left on the operator stack
        while oper_stack:
            oper = oper_stack.pop()
            arg2 = graph_stack.pop()
            arg1 = graph_stack.pop()
            apply_to_arg1 = Application(oper, arg1)
            apply_to_arg2 = Application(apply_to_arg1, arg2)
            graph_stack.append(apply_to_arg2)

        # when done the expression chain should have resolved to a single
        # graph, otherwise there was an error
        assert len(graph_stack) == 1
        return graph_stack[0]
    # end def visit_expr

    def visit_IDENT(self, node):
        # lookup the identifier in the context and return its graph
        return self.context[node.additional_info]

    def visit_NUMBER(self, node):
        return Value(intval=int(node.additional_info))

    def visit_STRING(self, node):
        return Value(strval=str(node.additional_info))

    def visit_CHAR(self, node):
        return Value(charval=str(node.additional_info))

#class Statement
