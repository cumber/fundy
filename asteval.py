
from pypy.rlib.parsing.tree import RPythonVisitor
from pypy.lang.fundy.graph import Value, Application, Lambda, ASSOC
from pypy.lang.fundy.builtin import default_context


class Eval(RPythonVisitor):
    """
    Evaluates fundy code in the form of a parse tree (see parse.py). There are
    two kinds of vist_* method: statement-level methods that must return None
    but may update self.context (name binding), and expression-level methods
    that return a graph (see graph.py), and may not update self.context (but
    may refer to it for name resolution).
    """
    def __init__(self, context=None):
        """
        context is the initial context to use; dictionary mapping strings to
        graph nodes
        """
        if context is None:
            self.context = default_context.copy()
        else:
            self.context = context.copy()
        
    def visit_program(self, node):
        for n in node.children:
            self.dispatch(n)

    def visit_print_statement(self, node):
        for n in node.children:
            graph = self.dispatch(n)
            graph.reduce_full()
            # graph should now be a value node
            print graph.value.to_string()
    
    def visit_def_statement(self, node):
        if node.children[2].symbol == 'type_decl':
            ident, paramlist, type_decl, block = node.children
        else:
            ident, paramlist, block = node.children
            type_decl = None
            
        if paramlist.children:
            sub_eval = Eval(self.context)
            base_lambda = sub_eval.dispatch(paramlist)
            tail_lambda = base_lambda
            while tail_lambda.body is not None:
                tail_lambda = tail_lambda.body
            tail_lambda.body = sub_eval.dispatch(block)
            self.context[ident.additional_info] = base_lambda
        else:
            # no parameters, so we don't need a lambda node at all, just bind
            # the name to the expression returned by evaluating the body
            self.context[ident.additional_info] = self.dispatch(block) 
    
    def visit_paramlist(self, node):
        base_lambda = self.dispatch(node.children[0])
        for n in node.children[1:]:
            base_lambda.body = self.dispatch(n)
        return base_lambda
    
    def visit_param(self, node):
        new_lambda = Lambda()
        self.context[node.children[0].additional_info] = new_lambda
        return new_lambda
    
    def visit_block(self, node):
        # last item is the expression to be returned, any other items
        # are name binding statements for the current context
        for i in xrange(len(node.children) - 1):
            self.dispatch(node.children[i])
        return self.dispatch(node.children[-1])
    
    def visit_assign_statement(self, node):
        ident, expr = node.children
        self.context[ident.additional_info] = self.dispatch(expr)
        
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
                                (functor.assoc is ASSOC.LEFT and
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
        return self.context[node.additional_info]

    def visit_NUMBER(self, node):
        return Value(intval=int(node.additional_info))

    def visit_STRING(self, node):
        return Value(strval=str(node.additional_info))

    def visit_CHAR(self, node):
        return Value(charval=str(node.additional_info))

