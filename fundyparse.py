
from pypy.rlib.parsing.ebnfparse import parse_ebnf, check_for_missing_names
from pypy.rlib.parsing.parsing import PackratParser, ParseError
from pypy.rlib.parsing.lexer import Lexer, Token, SourcePos

import py
import sys


def get_grammar():
    """
    NOT_RPYTHON: This function is only called to process the grammarfile, which
    occurs before translation, so it does not need to be RPython.
    """
    # globals is not actually used here directly but needed in the environment
    # to allow #!if directives in the grammar file to access it.
    import globals

    grammarfile = py.magic.autopath().dirpath().join('fundy.grammar')
    lines = []
    skipdepth = 0
    for line in grammarfile.readlines():
        if skipdepth is not 0:
            if line.startswith('#!endif'):
                skipdepth -= 1
            continue    # we're in a false #!if, keep going

        if line.startswith('#!if '):
            condition = line.lstrip('#!if ').strip()
            if not eval(condition):
                skipdepth += 1
            continue

        lines.append(line)
    # end for

    grammar = '\n'.join(lines)

    try:
        regexes, rules, ToAST = parse_ebnf(grammar)
    except ParseError, e:
        print e.nice_error_message(filename=str(grammarfile), source=grammar)
        sys.exit(1)

    return regexes, rules, ToAST


# similar to ebnfparse.make_parse_function, but accepts a function to
# run the lexer's token stream through before passing it to the parser,
# and a list of extra names that are added by the post-processing stage
def make_messy_parse_function(res, rules, eof=False, post_lexer=None,
                              extra_names=()):
    """
    NOT_RPYTHON: This function is only called to process the grammarfile, which
    occurs before translation, so it does not need to be RPython.

    The parse function it returns parses Fundy code into a "messy" AST, which
    can be cleaned up using the ToAST object obtained from parse_ebnf(grammar).
    """
    names, res = zip(*res)
    if "IGNORE" in names:
        ignore = ["IGNORE"]
    else:
        ignore = []
    check_for_missing_names(names + extra_names, res, rules)
    lexer = Lexer(list(res), list(names), ignore=ignore)
    parser = PackratParser(rules, rules[0].nonterminal)
    def parse(s):
        tokens = lexer.tokenize(s, eof=eof)
        if post_lexer is not None:
            tokens = post_lexer(tokens)
        s = parser.parse(tokens)
        return s

    return parse


def process_indentation(tokens):
    """
    Remove LINEBREAK tokens from a token stream, inserting TERM where needed.

    A LINEBREAK token is assumed to be produced for every sequence of whitespace
    containing one or more newlines. It is also assumed that it is impossible
    for two LINEBREAK tokens to appear consecutively, since they would be read
    as one multi-line LINEBREAK.

    All whitespace up to and including the last newline is ignored, and the
    length of the remaining text (plus 3 times the numeber of tabs to bring the
    indent level for tabs to 4 spaces) is taken as the indent level of the line.

    The current indentation level is the top value in the indentation stack.

    When a line is indented more than the current indentation level, the
    LINEBREAK token is simply removed.

    When a line is indented equal to the current indentation level, a TERM token
    is inserted into the token stream.

    When a BEGIN token is encountered, if the next line is indented more than
    the current indentation level, its indentation level is pushed onto the
    indentation stack.

    When a line is indented less than the current indentation level, the
    indentation stack is popped until the current indentation level is less than
    the indentation of the line. For each value popped, a TERM token is inserted
    into the token stream, plus one additional TERM. i.e. one TERM for not being
    indented, as normal, plus one for each dedent.

    NOTE: this function is called at runtime, so it must be RPython.
    """
    stack = [0]
    ret = []
    begin_block = False
    for tok in tokens:
        if tok.name == 'BEGIN':
            begin_block = True
            ret.append(tok)

        elif tok.name == 'LINEBREAK':
            indentstr = tok.source.split('\n')[-1]
            indent = len(indentstr) + indentstr.count('\t')*3

            if indent <= stack[-1]:
                ret.append(Token('TERM', tok.source, tok.source_pos))
                if begin_block:
                    # If we were supposed to begin a block but there was no
                    # indent, then the block finished on the same line as it
                    # started, so we need to emit an extra TERM to complete it.
                    ret.append(Token('TERM', tok.source, tok.source_pos))
                while indent < stack[-1]:
                    stack.pop()
                    ret.append(Token('TERM', tok.source, tok.source_pos))

            if indent > stack[-1]:
                if begin_block:
                    stack.append(indent)

            # Regardless of the indentation level, after processing a newline
            # we're no longer looking to start a new block.
            begin_block = False

        elif tok.name == 'EOF':
            while stack:
                stack.pop()
                ret.append(Token('TERM', tok.source, tok.source_pos))
            ret.append(tok)

        else:
            ret.append(tok)
    # end for tok in tokens

    return ret
# end def process_indentation


def make_parse_function():
    """
    Convenience function. Goes the whole way from reading the grammar file to
    building a function that parses Fundy code into the sort of AST that the
    asteval module expects. Not called at runtime, so it does not need to be
    RPython, but the function it returns is.
    """
    regexes, rules, ToAST = get_grammar()
    messy_parse = make_messy_parse_function(regexes, rules, eof=True,
                                            post_lexer=process_indentation)
    tidyer = ToAST()

    def parse(code):
        messy_tree = messy_parse(code)
        tidy_tree = tidyer.transform(messy_tree)
        return tidy_tree

    return parse

# Here we actually build the RPython parsing function that can be imported
# from this module. Yay!
parse = make_parse_function()


def show_parse(code):
    """
    NOT_RPYTHON: For testing/debugging use
    """
    try:
        parse(code).view()
    except ParseError, e:
        print e.nice_error_message(source=code)
