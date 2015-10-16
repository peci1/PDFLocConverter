#!/usr/bin/env python
import collections
import logging

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LTContainer, LTChar, LTTextLine, LTText, LTPage, LTFigure
from pdfminer.pdfinterp import PDFPageInterpreter, PDFInterpreterError, LITERAL_FORM
from pdfminer.pdftypes import stream_value, list_value, dict_value
from pdfminer.psparser import literal_name, STRICT
from pdfminer.utils import MATRIX_IDENTITY, mult_matrix

from pdfloc_converter.pdfloc import BoundingBoxOnPage

__author__ = 'Martin Pecka'


class PDFLocDocument(LTContainer):
    def __init__(self):
        super(PDFLocDocument, self).__init__((0.0, 0.0, 1.0, 1.0))
        self.index_in_layout_parent = 0
        self.layout_children = []
        self.layout_parent = None

    def add(self, page):
        assert isinstance(page, PDFLocPage)
        super(PDFLocDocument, self).add(page)

        page.index_in_layout_parent = len(self.layout_children)
        page.layout_parent = self
        self.layout_children.append(page)

    def find_bboxes_between_chars(self, start_char, end_char):
        assert isinstance(start_char, LTChar)
        assert isinstance(end_char, LTChar)
        assert hasattr(start_char, "layout_parent")
        assert hasattr(end_char, "layout_parent")

        start_line = start_char.layout_parent
        end_line = end_char.layout_parent

        lines = [start_line]

        if start_line == end_line:
            return lines

        node = start_line
        i = 0
        came_from_child = False
        while node is not None and node != end_line and i < 100000:
            if not came_from_child and len(node.layout_children) > 0 and isinstance(node.layout_children[0], LTContainer):
                node = node.layout_children[0]
                came_from_child = False
                if isinstance(node, LTTextLine):
                    lines.append(node)
            elif node.layout_parent is not None and node.index_in_layout_parent < len(node.layout_parent.layout_children)-1:
                node = node.layout_parent.layout_children[node.index_in_layout_parent+1]
                came_from_child = False
                if isinstance(node, LTTextLine):
                    lines.append(node)
            elif node.layout_parent is not None:
                node = node.layout_parent
                came_from_child = True
            else:
                raise RuntimeError("End line not found: %s" % str(node))
            i += 1

        if len(lines) == 0:
            raise RuntimeError("No lines found for: start '%s', end '%s'" % (str(start_char), str(end_char)))

        bboxes = []
        for line in lines:
            pageid = self._get_page_for_page_item(line)
            bboxes.append(BoundingBoxOnPage(line.bbox, pageid, line.get_text()))

        # the first and last lines are not selected completely (note that this also works on a single line)
        bboxes[0].bbox = start_char.bbox[:2] + bboxes[0].bbox[2:]
        bboxes[len(bboxes)-1].bbox = bboxes[len(bboxes)-1].bbox[:2] + end_char.bbox[2:]

        start_i = start_char.index_in_layout_parent
        end_i = end_char.index_in_layout_parent
        if len(bboxes) == 1:
            bboxes[0].text = self._get_line_substring(lines[0], start_i, end_i)
        else:
            bboxes[0].text = self._get_line_substring(lines[0], start=start_i)
            bboxes[len(bboxes)-1].text = self._get_line_substring(lines[len(lines)-1], end=end_i)

        return bboxes

    def _get_line_substring(self, line, start=0, end=None):
        assert isinstance(line, LTTextLine)

        if end is None:
            end = len(line)

        text = ""
        i = 0
        for char in line:
            if start <= i <= end and isinstance(char, LTText):
                text += char.get_text()
            i += 1

        return text

    def find_bbox_for_char(self, char):
        assert isinstance(char, LTChar)
        pageid = self._get_page_for_page_item(char)
        return BoundingBoxOnPage(char.bbox, pageid, char.get_text())

    def _get_page_for_page_item(self, char_or_line):
        node = char_or_line
        while node is not None and not isinstance(node, PDFLocPage):
            node = node.layout_parent

        if node is None:
            return None
        return node.pageid


class PDFLocPage(LTPage):

    def __init__(self, pageid, bbox, rotate=0):
        super(PDFLocPage, self).__init__(pageid, bbox, rotate)

    def __getitem__(self, item):
        return self._objs[item]

    def analyze(self, laparams):
        super(PDFLocPage, self).analyze(laparams)

        self.layout_parent = None
        self.layout_children = self.groups
        self.index_in_layout_parent = 0

        i = 0
        if self.groups is not None:  # may be None for empty pages
            for child in self.groups:
                self._set_as_layout_parent(self, child, i)
                i += 1

    def _set_as_layout_parent(self, parent, child, index_in_layout_parent):
        child.layout_parent = parent
        child.layout_children = []
        child.index_in_layout_parent = index_in_layout_parent
        if isinstance(child, collections.Iterable):
            i = 0
            for grandchild in child:
                child.layout_children.append(grandchild)
                self._set_as_layout_parent(child, grandchild, i)
                i += 1

class PDFLocFigure(LTFigure):

    def __init__(self, name, bbox, matrix):
        super(PDFLocFigure, self).__init__(name, bbox, matrix)

    def __getitem__(self, item):
        return self._objs[item]

    def analyze(self, laparams):
        super(PDFLocFigure, self).analyze(laparams)

        self.layout_parent = None
        self.layout_children = self.groups
        self.index_in_layout_parent = 0

        i = 0
        if self.groups is not None:
            for child in self.groups:
                self._set_as_layout_parent(self, child, i)
                i += 1

    def _set_as_layout_parent(self, parent, child, index_in_layout_parent):
        child.layout_parent = parent
        child.layout_children = []
        child.index_in_layout_parent = index_in_layout_parent
        if isinstance(child, collections.Iterable):
            i = 0
            for grandchild in child:
                child.layout_children.append(grandchild)
                self._set_as_layout_parent(child, grandchild, i)
                i += 1

class PDFLocPageAnalyzer(PDFPageAggregator):
    def __init__(self, rsrcmgr, pageno=1, laparams=None):
        super(PDFLocPageAnalyzer, self).__init__(rsrcmgr, pageno, laparams)
        self.current_line = 0
        self.text_lines = {}
        self.coords_to_chars = {}
        self.interpreter = None
        self.cur_item = None

    def set_interpreter(self, interpreter):
        assert isinstance(interpreter, PDFLocInterpreter)
        self.interpreter = interpreter

    def begin_page(self, page, ctm):
        assert self.interpreter is not None
        super(PDFLocPageAnalyzer, self).begin_page(page, ctm)
        # custom class to add direct indexing of the contained objects
        self.cur_item = PDFLocPage(self.cur_item.pageid, self.cur_item.bbox)
        self.text_lines = {}
        self.coords_to_chars = {}

    def begin_figure(self, name, bbox, matrix):
        super(PDFLocPageAnalyzer, self).begin_figure(name, bbox, matrix)
        self.cur_item = PDFLocFigure(name, bbox, mult_matrix(matrix, self.ctm))

    def render_string(self, textstate, seq):
        self.current_line = self.interpreter.keyword_count+1
        self.text_lines[self.current_line] = []
        super(PDFLocPageAnalyzer, self).render_string(textstate, seq)

        line = self.text_lines[self.current_line]
        self.coords_to_chars[self.current_line] = []
        i = 0
        for str in seq:
            if isinstance(str, basestring):
                font = textstate.font
                char_map = []
                for cid in font.decode(str):
                    char_map.append(line[i])
                    i += 1
                self.coords_to_chars[self.current_line].append(char_map)

    def render_char(self, matrix, font, fontsize, scaling, rise, cid):
        result = super(PDFLocPageAnalyzer, self).render_char(matrix, font, fontsize, scaling, rise, cid)
        char = self.cur_item[len(self.cur_item)-1]
        self.text_lines[self.current_line].append(char)
        return result


class PDFLocInterpreter(PDFPageInterpreter):
    def __init__(self, rsrcmgr, device):
        PDFPageInterpreter.__init__(self, rsrcmgr, device)
        self.ignored_keywords = ["do_"+kw for kw in ["m", "l", "c", "v", "y", "h", "re", "n"]]
        self.keyword_count = 0
        # self.text_sequences = {}
        self.is_first_level_call = None

        # decorate the non-ignored keyword-processing functions so that they increment self.keyword_count
        for member in dir(self):
            if member.startswith("do_") and (member not in self.ignored_keywords):
                setattr(self, member, self.call_func_with_keyword_counting( getattr(self, member) ).__get__(self, self.__class__))

    def call_func_with_keyword_counting(self, func):
        def call_func_and_count_keyword(args):
            prev_is_first_level_call = self.is_first_level_call
            if self.is_first_level_call is None:
                self.is_first_level_call = True
            else:
                self.is_first_level_call = False

            func(*args)

            if self.is_first_level_call:
                self.keyword_count += 1

            self.is_first_level_call = prev_is_first_level_call

        if func.func_code.co_argcount == 0:
            def new_func():
                call_func_and_count_keyword([])
            return new_func
        if func.func_code.co_argcount == 1:
            def new_func(self):
                call_func_and_count_keyword([])
            return new_func
        if func.func_code.co_argcount == 2:
            def new_func(self, a1):
                call_func_and_count_keyword([a1])
            return new_func
        if func.func_code.co_argcount == 3:
            def new_func(self, a1, a2):
                call_func_and_count_keyword([a1, a2])
            return new_func
        if func.func_code.co_argcount == 4:
            def new_func(self, a1, a2, a3):
                call_func_and_count_keyword([a1, a2, a3])
            return new_func
        if func.func_code.co_argcount == 5:
            def new_func(self, a1, a2, a3, a4):
                call_func_and_count_keyword([a1, a2, a3, a4])
            return new_func
        if func.func_code.co_argcount == 6:
            def new_func(self, a1, a2, a3, a4, a5):
                call_func_and_count_keyword([a1, a2, a3, a4, a5])
            return new_func
        if func.func_code.co_argcount == 7:
            def new_func(self, a1, a2, a3, a4, a5, a6):
                call_func_and_count_keyword([a1, a2, a3, a4, a5, a6])
            return new_func

    def init_state(self, ctm):
        super(PDFLocInterpreter, self).init_state(ctm)
        self.keyword_count = 0
        # self.text_sequences = {}
        self.is_first_level_call = None

    def do_TJ(self, chain):
        super(PDFLocInterpreter, self).do_TJ(chain)

        if not self.is_first_level_call:
            return

        text_line = [s for s in chain if isinstance(s, basestring)]

        # self.text_sequences[self.keyword_count] = text_line

    # invoke an XObject
    def do_Do(self, xobjid):
        # the base of this function is basically copy-pasted from ancestor; unfortunately, I found no better solution
        xobjid = literal_name(xobjid)
        try:
            xobj = stream_value(self.xobjmap[xobjid])
        except KeyError:
            if STRICT:
                raise PDFInterpreterError('Undefined xobject id: %r' % xobjid)
            return
        if self.debug: logging.info('Processing xobj: %r' % xobj)
        subtype = xobj.get('Subtype')
        if subtype is LITERAL_FORM and 'BBox' in xobj:
            interpreter = self.dup()
            interpreter.is_first_level_call = None
            bbox = list_value(xobj['BBox'])
            matrix = list_value(xobj.get('Matrix', MATRIX_IDENTITY))
            # According to PDF reference 1.7 section 4.9.1, XObjects in
            # earlier PDFs (prior to v1.2) use the page's Resources entry
            # instead of having their own Resources entry.
            resources = dict_value(xobj.get('Resources')) or self.resources.copy()

            self.device.begin_figure(xobjid, bbox, matrix)
            interpreter.render_contents(resources, [xobj], ctm=mult_matrix(matrix, self.ctm))
            self.device.end_figure(xobjid)

            # for (k,v) in interpreter.text_lines.iteritems():
            #     self.text_sequences[k + self.keyword_count] = v
            self.keyword_count += interpreter.keyword_count
            print "Included %i keywords" % interpreter.keyword_count
        else:
            # ignored xobject type.
            pass
        return
