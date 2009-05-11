
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

fundy-%: *.py
	python $(PYPY_DIR)/pypy/translator/goal/translate.py $(OPT) $(BACKEND) $(BATCH) $(TRANSLATE_FLAGS) target_fundy
