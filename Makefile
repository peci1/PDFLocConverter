##  Makefile (for maintainance purpose)
##

PACKAGE=pdfloc_converter

PYTHON=python2
GIT=git
RM=rm -f
CP=cp -f
MKDIR=mkdir

all:

install:
	$(PYTHON) setup.py install --home=$(HOME)

clean:
	-$(PYTHON) setup.py clean
	-$(RM) -r build dist MANIFEST
	-cd $(PACKAGE) && $(MAKE) clean

distclean: clean

sdist: distclean MANIFEST.in
	$(PYTHON) setup.py sdist
register: distclean MANIFEST.in
	$(PYTHON) setup.py sdist upload register