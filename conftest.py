"""
This is not a module of fundy, just configuration for the tests.

Should ideally live in the test directory, but it doesn't seem to work there
(adding options seems to be ignored unless you run py.test from the same
directory that has the conftest.py module, and running py.test from the test
directory fails due to the base fundy directory not being in path).
"""

import sys

import py


class ConftestPlugin(object):
    def pytest_addoption(self, parser):
        group = parser.addgroup('Fundy')
        group.addoption('-T', '--translate',
                        action='store_true', default=False,
                        help='Run tests on translated Fundy interpreter')

    def pytest_funcarg__fundy_cpython(self, pyfuncitem):
        return CPythonFuncarg(pyfuncitem)

    def pytest_funcarg__fundy_rpython(self, pyfuncitem):
        return RPythonFuncarg(pyfuncitem)

    def pytest_funcarg__fundy_translated(self, pyfuncitem):
        return TranslatedFuncarg(pyfuncitem)


class CPythonFuncarg(object):
    def __init__(self, pyfuncitem):
        name = pyfuncitem.name
        self.tempdir = pyfuncitem.config.mktemp(name, numbered=True)

    @staticmethod
    def raw_run(args):
        from interactive import main
        return main(['<fundy-test>'] + args)

    def run(self, args):
        try:
            return self.raw_run(args), None, None
        except Exception, e:
            return None, e, sys.exc_info()[2]

    def run_code(self, code):
        tmpfile = self.tempdir.join('tmp.fy')
        tmpfile.write(code)

        do_run = lambda: self.run([tmpfile.strpath])
        result, out, err = py.io.StdCaptureFD.call(do_run)

        ret, exc, tb = result
        return ret, out, err, exc, tb

class RPythonFuncarg(CPythonFuncarg):
    @staticmethod
    def raw_run(args):
        from interactive import main
        from utils import preparer
        preparer.prepare(for_translation=True)
        try:
            ret = CPythonFuncarg.raw_run(args)
        finally:
            preparer.prepare(for_translation=False)
        return ret

class TranslatedFuncarg(CPythonFuncarg):
    exe_wrapper = None

    def __init__(self, pyfuncitem):
        if not pyfuncitem.config.option.translate:
            py.test.skip('specify -T to run translated tests')
        super(TranslatedFuncarg, self).__init__(pyfuncitem)
        self.make()

    @classmethod
    def make(cls):
        if cls.exe_wrapper is None:
            from subprocess import check_call, CalledProcessError
            try:
                check_call(['make', 'fundy-c'])
            except CalledProcessError:
                @staticmethod
                def exe_wrapper(args):
                    py.test.fail('make failed first time; not re-running')
                cls.exe_wrapper = exe_wrapper
                raise
            else:
                @staticmethod
                def exe_wrapper(args):
                    exe_path = py.path.local('fundy-c').strpath
                    exe_and_args = [exe_path] + args
                    return check_call(exe_and_args)
                cls.exe_wrapper = exe_wrapper


    @classmethod
    def raw_run(cls, args):
        return cls.exe_wrapper(args)

