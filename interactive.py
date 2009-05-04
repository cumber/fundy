
import sys

from pypy.rlib.parsing.parsing import ParseError
from pypy.rlib.parsing.deterministic import LexerError
from pypy.rlib.streamio import DiskFile, construct_stream_tower

from asteval import Eval
from fundyparse import parse
from version import version_numbers

# use __stdin__ etc rather than stdin so it works in IDLE too
stdin_fd = DiskFile(sys.__stdin__.fileno())
stdout_fd = DiskFile(sys.__stdout__.fileno())
stderr_fd = DiskFile(sys.__stderr__.fileno())

stdin_stream = construct_stream_tower(stdin_fd, buffering=1, universal=True,
        reading=True, writing=False, binary=False)
stdout_stream = construct_stream_tower(stdout_fd, buffering=1, universal=True,
        reading=False, writing=True, binary=False)
stderr_stream = construct_stream_tower(stderr_fd, buffering=0, universal=True,
        reading=False, writing=True, binary=False)


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

    def push(self, line):
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        more = self.runsource(source, self.filename)
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
            if source.count('def') > source.count('return') or      \
               source.count('(') > source.count(')'):
                return None
            else:
                raise

        # no exception
        return tree

    def runsource(self, source, filename="<input>"):
        try:
            tree = self.compile(source)
        except LexerError, e:
            self.write(e.nice_error_message(filename=filename))
        except ParseError, e:
            self.write(e.nice_error_message(filename=filename,
                                            source=source))
        else:
            if tree is None:
                return True     # incomplete input
            else:
                self.runcode(tree)

        # compile error or successfully ran
        return False

    def runcode(self, tree):
        self.asteval.dispatch(tree)




def main():
    interp = FundyConsole()
    interp.interact()


if __name__ == '__main__':
    main()
