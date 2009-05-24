"""
Tests of running fundy level code against expected output.
"""

import sys

import py


class Snippet(object):
    def __init__(self, code, expect='', err_expect=''):
        self.code = code
        self.expect = expect
        self.err_expect = err_expect

    def test(self, interpreter):
        return_code, out, err = interpreter.run_code(self.code)

        out = out.strip()
        err = err.strip()
        expect = self.expect.strip()
        err_expect = self.err_expect.strip()

        print '==================== code was ===================='
        print self.code
        print '=================== stdout was ==================='
        print out
        print '==================== expected ===================='
        print expect
        print '=================================================='

        print >> sys.stderr, \
              '=================== stderr was ==================='
        print >> sys.stderr, err
        print >> sys.stderr, \
              '==================== expected ===================='
        print >> sys.stderr, err_expect
        print >> sys.stderr, \
              '=================================================='

        assert out == expect
        assert err == err_expect

    def make_tests(self, xfail=None, xfail_cpython=None, xfail_rpython=None,
                   xfail_translated=None,
                   no_cpython=None, no_rpython=None, no_translated=None):
        """
        Return a generative test function that returns tests running the snippet
        through three fundy interpreters: running on top of CPython, running
        on top of CPython but setup to be RPython-compliant, and translated.

        The three tests can be marked as expected to fail altogether or
        individually, and can set to not use any of three interpreters.
        """
        # Convenience function; marks a test as expected to fail if a reason
        # is provided.
        def mark(test, xfail_specific, xfail_general):
            if xfail_specific is not None:
                return py.test.mark.xfail(xfail_specific)(test)
            elif xfail_general is not None:
                return py.test.mark.xfail(xfail_general)(test)
            else:
                return test

        # Make each test function take a funcarg that will give it access
        # to the appropriate interpreter.
        test_cpython = lambda fundy_cpython: self.test(fundy_cpython)
        test_rpython = lambda fundy_rpython: self.test(fundy_rpython)
        test_translated = lambda fundy_translated: self.test(fundy_translated)

        # The generator function we have to return
        def generator_func():
            if not no_cpython:
                yield 'cpython', mark(test_cpython, xfail_cpython, xfail)
            if not no_rpython:
                yield 'rpython', mark(test_rpython, xfail_rpython, xfail)
            if not no_translated:
                yield 'translated', mark(test_translated, xfail_translated,
                                         xfail)

        return generator_func


    def __repr__(self):
        if self.err_expect:
            return 'Snippet(%r, %r, %r)' % \
                (self.code, self.expect, self.err_expect)
        elif self.expect:
            return 'Snippet(%r, %r)' % (self.code, self.expect)
        else:
            return 'Snippet(%r)' % self.code


test_int_arith = Snippet('print 1 + 2 * 3 - 4', '3').make_tests()

test_bool = Snippet('print true and false', 'true').make_tests(
    xfail="bools don't print yet")

test_var = Snippet('''
x = 3 - 8
print x
''', '-5').make_tests()

test_func = Snippet('''
plus x y = x + y
plus1 = plus 1
print plus 9 3
print plus1 10
''',
'''
12
11
''').make_tests()

test_def = Snippet('''
def plus2 x:
    y = x + 1
    z = y + 1
    return z
print plus2 100
''',
'''
102
''').make_tests()

test_sub_def = Snippet('''
def plus2 x:
    def plus1 x:
        z = x + 1
        return z
    return plus1 (plus1 x)
print plus2 100
''',
'''
102
''').make_tests()

test_typeswitch = Snippet('''
i = 3
b = true
u = unit
c = '@'
s = "foo"

def gettype thing:
    return typeswitch thing:
        case int return "int"
        case bool return "bool"
        case unittype return "unit"
        case char return "char"
        case string return "string"

print gettype i
print gettype b
print gettype u
print gettype c
print gettype s
''',
'''
int
bool
unit
char
string
''').make_tests()

test_typeswitch2 = Snippet('''
typeswitch 3:
    case int return "int"

print 8

z = typeswitch 9:
    case int return "another int"

print z
''',
'''
int
8
another int
''').make_tests()
