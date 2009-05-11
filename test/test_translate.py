
from pypy.translator.interactive import Translation

import globals
globals.setup_for_translation = True

from interactive import main


def test_translate():
    t = Translation(main, [str])
    f = t.compile_c()
