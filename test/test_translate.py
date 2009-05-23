
from pypy.translator.interactive import Translation

def test_translate():
    from interactive import main
    from utils import preparer
    preparer.prepare(for_translation=True)

    t = Translation(main, [str])
    f = t.compile_c()
