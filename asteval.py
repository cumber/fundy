#
#   Copyright 2009 Benjamin Mellor
#
#   This file is part of Fundy.
#
#   Fundy is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from rpython.rlib.parsing.tree import RPythonVisitor, Symbol, Nonterminal

from utils import dotview, LabelledGraph, preparer
from graph import (Application, BuiltinNode, Lambda, Param, Cons, ConsNode,
                   Typeswitch, Y)
from builtin import default_context, IntPtr, CharPtr, StrPtr, unit
from pyops import ASSOC, FIXITY


class Expression(object):
    """
    Temporarily used to represent an expression object. Since operators can be
    added (or removed) at runtime, the parser cannot fully resolve expressions
    to an abstract syntax tree. Instead, the parser returns a tree representing
    expressions as elements chained together, where each element is something
    the front end of the parser does understand directly (including nested
    expressions in parentheses). It is the responisibility of this class to
    convert a chain of these expression elements into the appropriate graph
    structure, taking into account operator associativity and precedence.

    NOTE: the algorithm used here is "top down operator precedence" as described
    at http://effbot.org/zone/simple-top-down-parsing.htm, but heavily modified
    to account for the fact that every "token" can be considered an operator.
    """
    def __init__(self, eval, nodes):
        self.eval = eval
        self.elements = list(nodes)

    def __repr__(self):
        """
        NOT_RPYTHON:
        """
        return 'Expression(<Eval>, %r)' % self.elements

    def end(self):
        return not self.elements

    def peek(self):
        return self.elements[0]

    def advance(self):
        return self.elements.pop(0)

    def resolve(self, rbp=0):
        if self.end():
            return None

        tmp = self.advance()
        left = self.nud(tmp)

        while not self.end() and rbp < self.lbp(self.peek()):
            tmp = self.advance()
            left = self.led(tmp, left)

        return left

    def nud(self, node):
        return self.eval.dispatch(node)

    def led(self, node, left):
        # When we call here, we need to check what kind of operator node is.
        # If infix, then we apply it to left (given) and right (call resolve
        # recursively to get it).
        # If postfix, we apply it to left and return without evaluation right
        # (that will be done at a higher level).
        # If prefix (remember that everything is a prefix operator unless
        # explicitly declared otherwise), we apply left to it and return that.

        rbp, assoc, fix = self.get_binding_power_assoc_fixity(node)
        # pass a value less than our binding power to the recursive call
        # to get right associativity
        if assoc is ASSOC.RIGHT:
            rbp = rbp -1


        this = self.eval.dispatch(node)
        if fix is FIXITY.PREFIX:
            applied = Application(left, this)
        elif fix is FIXITY.POSTFIX:
            applied = Application(this, left)
        else:   # infix
            right = self.resolve(rbp)
            if right is None:
                applied = Application(this, left)
            else:
                applied = Application(Application(this, left), right)

        return applied

    def get_binding_power_assoc_fixity(self, node):
        if node.symbol == 'IDENT':
            assert isinstance(node, Symbol)
            name = node.additional_info
            if self.eval.context.is_operator(name):
                prec = self.eval.context.get_prec(name)
                assoc = self.eval.context.get_assoc(name)
                fixity = self.eval.context.get_fixity(name)
                return prec, assoc, fixity

        # Default precedence and associativity for function application, since
        # every term that is not explicitly a name for an operator is parsed
        # as if it were an ordinary function.
        return 10000, ASSOC.LEFT, FIXITY.PREFIX

    def lbp(self, node):
        lbp, _, _ = self.get_binding_power_assoc_fixity(node)
        return lbp


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

    def visit_show_statement(self, node):
        # See the docstrings of the following two methods for explanation.
        return self.__hack__real_visit_show_statement(node)

    def __hack__real_visit_show_statement(self, node):
        """
        NOT_RPYTHON: Visually display the argument expressions as graphs.

        The show statement is for debugging/educational purposes, and the
        current implementation can only be used when running Fundy on top of
        CPython.
        """
        lgs = [LabelledGraph(self, astexpr=n) for n in node.children]
        if not lgs:
            # no arguments to show given; show entire context
            lgs = [LabelledGraph(self, graph=g, label=n)
                   for (n, g) in self.context.items()]
        dotview(*lgs)

    @classmethod
    def _fix_for_translation(cls, for_translation):
        """
        NOT_RPYTHON: The show statement is not implemented in an RPython-safe
        way, and cannot be used when running translated. This method patches
        the class' visit_show_statement method to do nothing, or to do its real
        job.

        NOTE: We go about the patching strangely. The visit_show_statement
        method cannot simply be deleted, because the important thing is not
        whether the method exists on the class, but whether it exists in the
        dispatch table that is generated from the class dictionary by the
        metaclass of the RPythonVisitor base class. Even though it will never
        be called when the grammar does not include the show statement, the
        translator cannot prove this, and so tries to analyse it.

        The dispatch table is stored in a local variable of the function that
        generated the dispatch method, so is essentially impossible to access.
        We could regenerate the dispatch table, but that is difficult,
        introduces unnecessary dependancies on the internals of the
        RPythonVisitor implementation, and seems like overkill.

        Therefore, visit_show_statement must be untouched, and forwards to
        __hack__real_visit_show_statement, which we CAN alter here. It must
        exist, but we replace it with a do nothing method when preparing for
        translation.
        """
        if for_translation:
            cls.__hack__real_visit_show_statement = lambda self, node: None
        else:
            cls.__hack__real_visit_show_statement = cls.__secret_backup

    __secret_backup = __hack__real_visit_show_statement


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

        # Here we assume that the definition may be recursive; use Y to make
        # an equivalent non-recursive definition by factoring out the function
        # to call recursively as an extra parameter, then binding the name
        # being defined to that parameter in the local scope. If in fact that
        # name is never dereferenced, then we waste a bit of work reducing the
        # Y application, but it reduces to what the graph would've been if we
        # didn't assume it was recursive after only one step (creates some
        # extra garbage though).
        recursion_marker = Param()
        local_scope.context.bind(name, recursion_marker)

        graph = local_scope.make_lambda_chain(params, block)

        graph = Application(Y, Lambda(recursion_marker, graph))

        # bind the name in the original scope
        self.context.bind(name, graph)

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

    def visit_typeswitch(self, node):
        expr = self.dispatch(node.children[0])
        cases = [self.dispatch(n) for n in node.children[1:]]
        return Application(Typeswitch(cases), expr)

    def visit_switchcase(self, node):
        """
        Return a Cons node of the case expression and the return expression.
        """
        case, ret = node.children
        return Cons(self.dispatch(case), self.dispatch(ret))

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
        return Expression(self, node.children).resolve()

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

# end class Eval


# Register a funciton that switches between translation mode and CPython mode.
preparer.register(Eval._fix_for_translation)

