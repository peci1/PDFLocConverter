#!/usr/bin/env python
import sys
import codecs

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

from pdfloc_converter.converter import PDFLocConverter

__author__ = 'Martin Pecka'


# main
def main(argv):
    debug = 1
    #
    PDFDocument.debug = debug
    PDFParser.debug = debug

    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr)

    fname = argv[1]
    pdfloc_start = argv[2]
    pdfloc_end = argv[3]

    bboxes = PDFLocConverter.pdflocs_to_bboxes(fname, [(pdfloc_start, pdfloc_end)])
    for bboxes_list in bboxes:
        for bbox in bboxes_list:
            print bbox

    return

if __name__ == '__main__':
    sys.exit(main(sys.argv))
