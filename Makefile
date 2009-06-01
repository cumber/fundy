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

# Defualt place to look for PyPy being installed.
PYPY_DIR :=	~/pypy-1.1.0/

# Set target-specific variable to set the translation backend based on the name
# of the target, e.g. fundy-jvm uses the jvm backend.
fundy-%: BACKEND =	--backend=$(@:fundy-%=%)

# Default optimization level.
OPT :=	--opt=3

# Set other options for translate.py.
TRANSLATE_FLAGS :=

# Set INTERACTIVE to drop into the pdb shell after translating.
INTERACTIVE	:=

ifdef INTERACTIVE
	BATCH :=
else
	BATCH :=	--batch
endif

# Default target: fundy translated with the C backend.
.PHONY: default
default: fundy-c

fundy-%: *.py fundy.grammar
	python $(PYPY_DIR)/pypy/translator/goal/translate.py $(OPT) $(BACKEND) $(BATCH) $(TRANSLATE_FLAGS) target_fundy
