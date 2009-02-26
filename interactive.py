
from pypy.lang.fundy.asteval import Eval
from pypy.lang.fundy.fundyparse import parse
from pypy.rlib.parsing.parsing import ParseError
from pypy.rlib.parsing.deterministic import LexerError

def interactive_loop():
    eval = Eval()
    while True:
        try:
            st = raw_input('|> ')
            while True:
                line = raw_input('.. ')
                if not line:
                    break
                st = st + '\n' + line
            st = st + '\n'
            try:
                tree = parse(st)
                eval.dispatch(tree)
            except ParseError, e:
                print e.nice_error_message(filename='console', source=st)
            except LexerError, e:
                print e.nice_error_message(filename='console')
        except EOFError:
            break
        

if __name__ == '__main__':
    interactive_loop()
