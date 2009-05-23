"""
This file is not a module of Fundy. It defines the target spec for th PyPy
translation process.
"""

# _____ Define and setup target ___

def target(driver, args):
    from interactive import main
    from utils import preparer
    preparer.prepare(for_translation=True)
    driver.exe_name = 'fundy-%(backend)s'
    print args
    return main, None
