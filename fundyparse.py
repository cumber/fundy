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

import py
import sys

from pypy.rlib.parsing.ebnfparse import parse_ebnf, check_for_missing_names
from pypy.rlib.parsing.parsing import PackratParser, ParseError
from pypy.rlib.parsing.lexer import Lexer, Token, SourcePos

from utils import preparer


def get_grammar(for_translation):
    """
    NOT_RPYTHON: This function is only called to process the grammarfile, which
    occurs before translation, so it does not need to be RPython.

    The for_translation argument should be True if the grammar should be built
    for translating the Fundy interpreter to low level code, or False for
    running on top of CPython.
    """
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


# Similar to ebnfparse.make_parse_function, but accepts a function to
# run the lexer's token stream through before passing it to the parser,
# and a list of extra names that are added by the post-processing stage.
def make_messy_parse_function(regexes, rules, eof=False, post_lexer=None,
                              extra_names=()):
    """
    NOT_RPYTHON: This function is only called to process the grammarfile, which
    occurs before translation, so it does not need to be RPython.

    The parse function it returns parses Fundy code into a "messy" AST, which
    can be cleaned up using the ToAST object obtained from parse_ebnf(grammar).
    """
    names, regexes = zip(*regexes)
    if "IGNORE" in names:
        ignore = ["IGNORE"]
    else:
        ignore = []
    check_for_missing_names(names + extra_names, regexes, rules)
    lexer = Lexer(list(regexes), list(names), ignore=ignore)
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


def make_parse_function(for_translation):
    """
    Convenience function. Goes the whole way from reading the grammar file to
    building a function that parses Fundy code into the sort of AST that the
    asteval module expects. Not called at runtime, so it does not need to be
    RPython, but the function it returns is.
    """
    regexes, rules, ToAST = get_grammar(for_translation)
    messy_parse = make_messy_parse_function(regexes, rules, eof=True,
                                            post_lexer=process_indentation)
    tidyer = ToAST()

    def parse(code):
        messy_tree = messy_parse(code)
        tidy_tree = tidyer.transform(messy_tree)
        return tidy_tree

    return parse


class __SecretParser(object):
    def __init__(self):
        """
        NOT_RPYTHON: This class exists to encapsulate the state of the parser,
        which can either be in translated mode or untranslated mode, since the
        show statement can only be supported when running on top of CPython.

        The parse function exported from this module calls out to an instance
        of this class, allowing other modules to be ignorant of the fact that
        this is parameterised on whether we're translating or not. Although
        this class is not RPython in its entirety (because the process of
        building a parser is not), when analyzing the parse method the
        appropriate parse function will already be built.

        I'm reasonably sure the if statement in the parse method will not
        appear in the translated interpreter either (nor will two copies of
        the parse function and grammar), since self.for_translation will be
        a constant from the point of view of the translator?
        """
        self.for_translation = False
        self.setup(self.for_translation)

    def setup(self, for_translation):
        """
        NOT_RPYTHON:
        """
        self.for_translation = for_translation
        if for_translation:
            attr = 'translated_parse'
        else:
            attr = 'untranslated_parse'

        if getattr(self, attr, None) is None:
            setattr(self, attr, make_parse_function(for_translation))

    def parse(self, code):
        if self.for_translation:
            return self.translated_parse(code)
        else:
            return self.untranslated_parse(code)


__secret_parser_state = __SecretParser()
preparer.register(__secret_parser_state.setup)

# This is the actual parse function that other modules can import from here.
# (finally!)
def parse(code):
    return __secret_parser_state.parse(code)


def show_parse(code):
    """
    NOT_RPYTHON: For testing/debugging use
    """
    try:
        parse(code).view()
    except ParseError, e:
        print e.nice_error_message(source=code)
