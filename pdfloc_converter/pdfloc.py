import re

__author__ = 'Martin Pecka'


class PDFLoc(object):
    _regex_matcher = re.compile(
        r"#pdfloc\("
            r"(?P<hash>[0-9a-h]+),"
            r"(?P<page>[0-9]+),"
            r"(?P<keyword_num>[0-9]+|E),"
            r"(?P<string_num>[0-9]+|E),"
            r"(?P<instring_num>[0-9]+|E),"
            r"(?P<flag1>[01]),"
            r"(?P<is_up_to_end>[01]),"
            r"(?P<is_not_up_to_end>[01])"
        r"\)", re.IGNORECASE)

    #pdfloc(hash, page, keyword_num, string_num, instring_num, ?, is_up_to_end, is_not_up_to_end)
    # keyword_num: poradi, kolikaty keyword to je v aktualnim streamu (nutno resolvovat Do direktivy)
    # string_num: kolikata zavorka to je
    # instring_num: kolikaty znak v zavorce to je
    # is_up_to_end: pokud je 1, tak jsou predchozi E a oznacuje konec streamu

    def __init__(self, pdfloc):
        match = PDFLoc._regex_matcher.match(pdfloc)

        if match is not None:
            self._hash = str(match.group("hash"))
            self._page = int(match.group("page"))
            self._keyword_num = int(match.group("keyword_num")) if (match.group("keyword_num") != "E") else None
            self._string_num = int(match.group("string_num")) if (match.group("string_num") != "E") else None
            self._instring_num = int(match.group("instring_num")) if (match.group("instring_num") != "E") else None
            self._flag1 = bool(match.group("flag1"))
            self._is_up_to_end = bool(match.group("is_up_to_end"))
            self._is_not_up_to_end = bool(match.group("is_not_up_to_end"))
        else:
            raise ValueError("The following pdfloc couldn't be parsed: %s" % pdfloc)

    @property
    def hash(self):
        return self._hash

    @property
    def page(self):
        return self._page

    @property
    def keyword_num(self):
        return self._keyword_num

    @property
    def string_num(self):
        return self._string_num

    @property
    def instring_num(self):
        return self._instring_num

    @property
    def flag1(self):
        return self._flag1

    @property
    def is_up_to_end(self):
        return self._is_up_to_end

    @property
    def is_not_up_to_end(self):
        return self._is_not_up_to_end

    def __str__(self):
        return "#pdfloc(%s,%d,%d,%d,%d,%d,%d,%d)" % (
            self.hash, self.page, self.keyword_num, self.string_num, self.instring_num, self.flag1,
            self.is_up_to_end, self.is_not_up_to_end
        )


class PDFLocPair(object):
    def __init__(self, start, end):
        super(PDFLocPair, self).__init__()
        self.start = PDFLoc(start)
        self.end = PDFLoc(end)

    @property
    def pages_covered(self):
        return range(self.start.page, self.end.page+1)

    def __str__(self):
        return str(self.start) + ";" + str(self.end)


class PDFLocBoundingBoxes(object):
    def __init__(self, bboxes, page=None):
        super(PDFLocBoundingBoxes, self).__init__()

        assert isinstance(bboxes, list)

        if len(bboxes) == 0:
            return

        if isinstance(bboxes[0], tuple) and page is not None:
            self.bboxes = [BoundingBoxOnPage(b, page) for b in bboxes]
        elif isinstance(bboxes[0], BoundingBoxOnPage):
            self.bboxes = bboxes

    @property
    def pages_covered(self):
        return set([bbox.page for bbox in self.bboxes])


class BoundingBoxOnPage(object):
    def __init__(self, bbox, page, text=None):
        super(BoundingBoxOnPage, self).__init__()

        assert isinstance(bbox, tuple)
        assert isinstance(page, int)

        self.bbox = bbox
        self.page = page
        self.text = text

    def __repr__(self):
        return "Page %i, '%s', %s" % (self.page, str(self.bbox), self.text.encode("ascii", "ignore"))

    def __str__(self):
        return self.__repr__()


