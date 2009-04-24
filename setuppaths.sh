# source this file in a shell to get PYTHONPATH to include pypy and fundy

PYTHONPATH="`pwd`:`pwd`/../pypy:${PYTHONPATH}"
