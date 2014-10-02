.PHONY: clean fundy-c test

all: fundy-c

clean:
	@rm -f fundy-c

fundy-c:
	@rpython target_fundy.py

test:
	@py.test test
