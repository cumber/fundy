#
#   Copyright 2009 Benjamin Mellor
#
#   This file is part of Fundy.
#
#   Fundy is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

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
