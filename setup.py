#!/usr/bin/env python
from distutils.core import setup

from pdfloc_converter import __version__

setup(
    name='pdfloc_converter',
    version=__version__,
    description='PDFLoc location converter',
    long_description='''PDFLoc location converter''',
    license='BSD',
    author='Martin Pecka',
    author_email='peci1 at seznam dot cz',
    url='',
    packages=[
        'pdfloc_converter',
    ],
    keywords=['pdfloc', 'pdf converter'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Topic :: Utilities',
    ],
    requires=['pdfminer']
)
