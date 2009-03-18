import autopath

from pypy.translator.interactive import Translation

from pypy.lang.fundy.interactive import main


def test_translate():
    t = Translation(main, [])
    f = t.compile_c()
