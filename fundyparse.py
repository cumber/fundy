
from pypy.rlib.parsing.ebnfparse import parse_ebnf, check_for_missing_names
from pypy.rlib.parsing.parsing import PackratParser, ParseError
from pypy.rlib.parsing.lexer import Lexer, Token, SourcePos

import py
import sys

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

# similar to ebnfparse.make_parse_function, but accepts a function to
# run the lexer's token stream through before passing it to the parser,
# and a list of extra names that are added by the post-processing stage
def make_parse_function(res, rules, eof=False, post_lexer=None,
                        extra_names=()):
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


#def post_process(stream):
#    for tok in stream


parsef = make_parse_function(regexes, rules, eof=True)

def parse(code):
    t = parsef(code)
    return ToAST().transform(t)

def show_parse(code):
    try:
        t = parsef(code)
        ToAST().transform(t).view()
    except ParseError, e:
        print e.nice_error_message(source=code)
