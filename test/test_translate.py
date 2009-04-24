
from pypy.translator.interactive import Translation

from interactive import main


def test_translate():
    t = Translation(main, [])
    f = t.compile_c()
