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
        ret, out, err , exc, tb = interpreter.run_code(self.code)

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

        # If an exception occurred, re-raise it here, with the original
        # traceback so the point of failure can be seen. The reason we delayed
        # it until here was so that the IO capture could be reset and what
        # output was produced is printed, otherwise any debug prints would be
        # swallowed if an exception occurs.
        if exc is not None:
            raise exc, None, tb

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


#----------------------------------------------------------------------------#
# The actual tests now!                                                      #
#----------------------------------------------------------------------------#


# Simple test that arithmetic works, including operator precedence.
test_int_arith = Snippet('print 1 + 2 * 3 - 4', '3').make_tests()

test_bool = Snippet('print true and false', 'false').make_tests()

test_var = Snippet('''
x = 3 - 8
print x
''', '-5').make_tests()

# Simple function definition, including naming a partially applied function.
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

# Define a function using def, with a couple of local definitions.
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

# Use a def statement as a local definition in a def statement.
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

# Check that typeswitch works as expected.
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

# Typeswitches had some odd effects on the parser's ability to keep track of
# where semicolons should be inserted at one point. This exercises the parser
# (very slightly) more than the previous test.
test_typeswitch_parsing = Snippet('''
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

# Tests the order of application in an expression involving both arithmetic
# operators and function calls. The result was generated by running the same
# code through ghci.
test_func_expr = Snippet('''
inc = (+1)
z = 8 + inc 2 - 21 * inc 3
print z
''', '-73').make_tests()

# Exercises the equality operator. Only positive testing.
test_eq = Snippet('''
print 1 == 1
print 1 == 11

print 'g' == 'g'
print '%' == '9'

print "foo" == "foo"
print "bar" == "foo"

print unit == unit

print true == true
print true == false
''', '''
true
false
true
false
true
false
true
true
false
''').make_tests()

# Test that the equality operator will consider equal expressions that will
# only reduce to the same value, but are not already the same value node.
test_eq_complex = Snippet('''
inc = +1
by10 = *10

print 101 == inc (by10 10)
print by10 1 == inc (inc (inc 7))
''', '''
true
true
''').make_tests()

# Test if statement
test_if = Snippet('''
eq3 = ==3
print if (eq3 ((7 * 4 + 2) / 10))
    "yes"
    "no"
print if (true and false)
    "yes"
    "no"
''', '''
yes
no
''').make_tests()

# Test recursion
fac_args = [0, 1, 2, 4, 8, 16]

def fac(n):
    if n == 0:
        return 1
    else:
        return n * fac(n - 1)

test_fac = Snippet('''
fac n = if (0 == n)
           1
           (n * (fac (n - 1)))
''' + '\n'.join(['fac %d' % i for i in fac_args]),
'\n'.join([str(fac(i)) for i in fac_args])).make_tests()
