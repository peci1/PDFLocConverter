from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from pdfloc_converter.document_structure import NavigationTree
from pdfloc_converter.pdfloc import PDFLoc, PDFLocPair, PDFLocBoundingBoxes
from pdfloc_converter.pdfminer_extensions import PDFLocPageAnalyzer, PDFLocInterpreter, PDFLocDocument

__author__ = 'Martin Pecka'


class PDFLocConverter(object):
    def __init__(self, document, pdflocs=[], bboxes=[]):
        """
        Initialize the converter with the given document.

        If either pdflocs od bboxes are given, only their corresponding document
        pages will be parsed in the call to parse_document(). This is done to save
        CPU time and resources needed for parsing if only a small part of the document
        is needed.

        :param document: Either a prepared PDFDocument, or a string denoting a filename.
                         If a PDFDocument is given, the underlying parser's source stream
                            needs to be open for reading/seeking until parse_document()
                            is called.
                         If a filename is given, the PDFDocument is created here internally,
                            and the stream is closed as soon as parse_document() finishes.
        :type document: PDFDocument | basestring

        :param pdflocs: A list of PDFLocs of interest - only pages corresponding to them are
                            to be parsed.
        :type pdflocs: list

        :param bboxes: A list of bounding boxes of interest - only pages corresponding to
                            them are to be parsed.
        :type bboxes: list
        """
        super(PDFLocConverter, self).__init__()

        # if document is given as a filename and we open it automatically here,
        # we need to remember the file handle to close it when the document is parsed
        self.__source_file_handle = None

        if isinstance(document, PDFDocument):
            self._pdf_document = document
        elif isinstance(document, basestring):
            self.__source_file_handle = file(document, 'rb')
            parser = PDFParser(self.__source_file_handle)
            self._pdf_document = PDFDocument(parser)

        self._pdfloc_document = None
        self._only_pages = None
        self._navigation_tree = None

        self.restrict_only_on_pages_from(pdflocs, bboxes)

    def restrict_only_on_pages_from(self, pdflocs=[], bboxes=[], only_pages=set()):
        """
        Restrict parse_document() to only parse pages corresponding to the given PDFLocs'
        or boundingboxes' pages.

        If some restrictions were given in the constructor, this call will rewrite them.

        :param pdflocs: A list of PDFLocs of interest - only pages corresponding to them are
                            to be parsed.
        :type pdflocs: list

        :param bboxes: A list of bounding boxes of interest - only pages corresponding to
                            them are to be parsed.
        :type bboxes: list

        :param only_pages: The basic set of pages that are always parsed.
        :type only_pages: set

        :raises RuntimeError: If the document has already been parsed.
        """
        if self.is_document_parsed():
            raise RuntimeError("Cannot restrict pages in an already parsed document.")

        self._only_pages = set(only_pages)
        for pdfloc in pdflocs:
            if isinstance(pdfloc, PDFLoc):
                self._only_pages.add(pdfloc.page)
            elif isinstance(pdfloc, PDFLocPair):
                self._only_pages.update(pdfloc.pages_covered)

        for bbox in bboxes:
            if isinstance(bbox, PDFLocBoundingBoxes):
                self._only_pages.update(bbox.pages_covered)

        if len(self._only_pages) == 0:
            self._only_pages = None

    def is_document_parsed(self):
        """
        Return true if the document has already been parsed.
        :return: true if the document has already been parsed.
        :rtype bool:
        """
        return self._pdfloc_document is not None

    def parse_document(self):
        """
        Parse the document and prepare the internal PDFLoc-decoding structures.

        This function is only meant to be called once.

        Only close the document parser's source stream after calling this method.

        :raises RuntimeError: If this function is called more than once.
        :raises RuntimeError: If the document parser's source stream has already been closed.
        """

        if self.is_document_parsed():
            raise RuntimeError("parse_document can only be called once.")

        la = LAParams()
        rm = PDFResourceManager()
        dev = PDFLocPageAnalyzer(rm, laparams=la)
        interp = PDFLocInterpreter(rm, dev)
        dev.set_interpreter(interp)

        self._navigation_tree = NavigationTree()
        self._pdfloc_document = PDFLocDocument()

        for (pageno, page) in enumerate(PDFPage.create_pages(self._pdf_document)):

            if self._only_pages is not None and pageno not in self._only_pages:
                continue

            interp.process_page(page)

            self._navigation_tree[pageno] = dev.coords_to_chars
            self._pdfloc_document.add(dev.get_result())

            print "Page no. %i contains %i keywords" % (pageno, interp.keyword_count)

        # if we opened the source file, close it now, because we no longer need it
        if self.__source_file_handle is not None and not self.__source_file_handle.closed:
            self.__source_file_handle.close()

        # assert objs_per_page[0][73][0:2] == ["w","ork"]
        # assert objs_per_page[0][79][0] == "in"
        # assert objs_per_page[1][336][0] == "that"
        # assert objs_per_page[5][1296][0] == "Kno"
        # assert objs_per_page[6][400][0] == "solution"
        # assert objs_per_page[4][1278][0] == "A."
        # assert objs_per_page[3][2961][0:2] == [".", "F"]

    def pdfloc_pair_to_bboxes(self, pdfloc_pair):
        assert isinstance(pdfloc_pair, PDFLocPair)

        start_char = self._navigation_tree.find_layout_char(pdfloc_pair.start)
        end_char = self._navigation_tree.find_layout_char(pdfloc_pair.end)

        bboxes = self._pdfloc_document.find_bboxes_between_chars(start_char, end_char)
        return bboxes

    def pdfloc_to_xy(self, pdfloc):
        char = self._navigation_tree.find_layout_char(pdfloc)
        return self._pdfloc_document.find_bbox_for_char(char)

    def bboxes_to_pdfloc_pair(self, bboxes):
        pass  #TODO

    def xy_to_pdfloc(self, xy):
        pass  #TODO

    @staticmethod
    def pdflocs_to_bboxes(document, pdfloc_strings):
        """
        Parse the given document and return a list of bounding boxes corresponding to the
        given list of PDFLocs.

        :param document: Either a prepared PDFDocument, or a string denoting a filename.
        :type document: PDFDocument | basestring

        :param pdfloc_strings: A list of pairs (tuples) of strings with the PDFLocs.
        :type pdfloc_strings: list

        :return: The corresponding bounding boxes. There is a list of boundingboxes
                    corresponing to each one PDFLoc. Indices in the returned list
                    correspond to the order in which pdfloc_strings are iterated.
        :rtype list:
        """
        pdflocs = []
        for pdfloc_string in pdfloc_strings:
            if isinstance(pdfloc_string, tuple) and len(pdfloc_string) == 2:
                (start, end) = pdfloc_string
                pdflocs.append(PDFLocPair(start, end))
            else:
                print "Warning: ignoring pdfloc string '%s'" % pdfloc_string

        converter = PDFLocConverter(document, pdflocs)
        converter.parse_document()

        result = []
        for query in pdflocs:
            if isinstance(query, PDFLocPair):
                bboxes = converter.pdfloc_pair_to_bboxes(query)
                result.append(bboxes)

        return result