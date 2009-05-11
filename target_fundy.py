"""
This file is not a module of Fundy. It defines the target spec for th PyPy
translation process.
"""

# IMPORTANT! globals.setup_for_translation must be set to True before any other
# module is imported, so that all the module initialisation code sees the
# correct value of this global, in case any different action needs to be taken
# when translating than when running on top of CPython.
import globals
gloabls.setup_for_translation = True

# This is the funciton that will act as the entry point of the translated
# executable.
from interactive import main

# _____ Define and setup target ___

def target(driver, args):
    driver.exe_name = 'fundy-%(backend)s'
    print args
    return main, None
