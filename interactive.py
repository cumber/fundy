
import sys

from pypy.rlib.parsing.parsing import ParseError
from pypy.rlib.parsing.deterministic import LexerError
from pypy.rlib.streamio import open_file_as_stream, fdopen_as_stream

from asteval import Eval
from fundyparse import parse
from version import version_numbers

# Use __stdin__ etc rather than stdin so it works in IDLE too, although you
# have to interact with Fundy through the terminal that started IDLE, rather
# than IDLE's gui window.
stdin_stream = fdopen_as_stream(sys.__stdin__.fileno(), "rU", buffering=1)
stdout_stream = fdopen_as_stream(sys.__stdout__.fileno(), "wU", buffering=1)
stderr_stream = fdopen_as_stream(sys.__stderr__.fileno(), "wU", buffering=0)


class FundyConsole(object):
    def __init__(self, filename="<console>"):
        self.filename = filename
        self.asteval = Eval()
        self.stdin = stdin_stream
        self.stdout = stdout_stream
        self.stderr = stderr_stream
        self.resetbuffer()

    def resetbuffer(self):
        self.buffer= []

    def interact(self, banner=None, prompt='|> ', continue_prompt='.. '):
        if banner is None:
            self.write('Fundy %d.%d.%d\n' % version_numbers)
        else:
            self.write(banner + '\n')

        more = 0
        while True:
            try:
                if more:
                    line = self.raw_input(continue_prompt)
                else:
                    line = self.raw_input(prompt)
            except EOFError:
                self.write("\n")
                break
            else:
                more = self.push(line)

        # status code
        # TODO: make more informative
        return 0

    def push(self, line):
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        more = self.runsource(source)
        if not more:
            self.resetbuffer()
        return more

    def raw_input(self, prompt=""):
        #try:
            self.stdout.do_write(prompt)
            line = self.stdin.readline()
            if not line:
                raise EOFError
            elif line.endswith('\n'):
                line = line[:-1]    # remove trailing newline
            return line
        #except KeyboardInterrupt:
        #    raise

    def write(self, s):
        self.stderr.write(s)

    def compile(self, source):
        try:
            tree = parse(source + '\n')
        except ParseError, e:
            # HACK: If there are more def's than returns, or more open
            # parentheses than closed, then presume the parse error is because
            # of that and return None signalling that more input is required.
            # This allows such constructs to naturally be entered over several
            # lines interactively.
            if source.count('def') > source.count('return') or      \
               source.count('(') > source.count(')'):
                return None
            else:
                raise

        # no exception
        return tree

    def runsource(self, source):
        try:
            tree = self.compile(source)
        except LexerError, e:
            self.write(e.nice_error_message(filename=self.filename) + '\n')
        except ParseError, e:
            self.write(e.nice_error_message(filename=self.filename,
                                            source=source) + '\n')
        else:
            if tree is None:
                return True     # incomplete input
            else:
                self.runcode(tree)

        # compile error or successfully ran
        return False

    def runcode(self, tree):
        self.asteval.dispatch(tree)




def main(argv):
    if len(argv) > 1:
        # argv[0] is the executable name
        scriptname = argv[1]

        try:
            stream = open_file_as_stream(scriptname, mode="rU")
            try:
                source = stream.readall()
            finally:
                stream.close()
        except OSError, e:
            stderr_stream.write('Error reading file "%s" (errno: %d)\n'
                                % (scriptname, e.errno))
            return 1

        interp = FundyConsole(scriptname)
        interp.runsource(source)

        return 0
    else:
        interp = FundyConsole()
        return interp.interact()


if __name__ == '__main__':
    import sys
    main(sys.argv)
