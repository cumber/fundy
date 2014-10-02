.. _Python: https://www.python.org/
.. _virtualenv: https://pypy.python.org/pypi/virtualenv
.. _virtualenvwrapper: https://pypy.python.org/pypi/virtualenvwrapper


Fundy
=====

An interpreter for a dynamically typed functional programming language.

- https://github.com/cumber/fundy


.. warning:: fundy is a new programming language in early **Development**.

             DO NOT USE IN PRODUCTION!
             
             USE AT YOUR OWN RISK!


Prerequisites
-------------

It is recommended that you do all development using a Python Virtual
Environment using `virtualenv`_ and/or using the nice `virtualenvwrapper`_.

::
   
    $ mkvirtualenv fundy

You will need the `RPython <https://bitbucket.org/pypy/pypy>`_ toolchain
to build the interpreter. The easiest way to do this is to
`My Fork of PyPy <https://bitbucket.org/prologic/pypy>`_ which includes
a convenient ``setup-rpython.py`` to make working with the RPython toolchain
a bit easier.

::
    
    $ hg clone https://bitbucket.org/prologic/pypy
    $ cd pypy
    $ python setup-pypy develop
    $ python setup-rpython.py develop


Installation
------------

Grab the source from https://github.com/cumber/fundy and either
run ``python setup.py develop`` or ``pip install -r requirements.txt``

::
    
    $ git clone https://github.com/cumber/fundy
    $ cd fundy
    $ pip install -r requirements.txt


Building
--------

To build the interpreter simply run ``target_fundy.py`` against the RPython
Compiler. There is a ``Makefile`` that has a default target for building
and translating the interpreter.

::
    
    $ make


Usage
-----

You can either run the interpreter using `Python`_ itself or by running the
compiled interpreter ``fundy-c``.

::
    
    $ ./fundy-c

Untranslated running on top of `Python`_ (*CPython*):

::
    
    $ python interactive.py
