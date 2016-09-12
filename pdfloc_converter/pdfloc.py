import re

__author__ = 'Martin Pecka'


class PDFLoc(object):
    _regex_matcher = re.compile(
        r"#pdfloc\("
            r"(?P<hash>[0-9a-f]+),"
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

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class PDFLocPair(object):
    def __init__(self, start, end, comment=None):
        super(PDFLocPair, self).__init__()
        self.start = PDFLoc(start)
        self.end = PDFLoc(end)
        self.comment = comment

    @property
    def pages_covered(self):
        return range(self.start.page, self.end.page+1)

    def __str__(self):
        return str(self.start) + ";" + str(self.end) + ((" " + self.comment) if self.comment is not None else "")

    def __eq__(self, other):
        if not isinstance(other, PDFLocPair):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class PDFLocBoundingBoxes(object):
    def __init__(self, bboxes, page=None, comment=None):
        super(PDFLocBoundingBoxes, self).__init__()

        assert isinstance(bboxes, list)

        if len(bboxes) == 0:
            return

        if isinstance(bboxes[0], tuple) and page is not None:
            self.bboxes = [BoundingBoxOnPage(b, page) for b in bboxes]
        elif isinstance(bboxes[0], BoundingBoxOnPage):
            self.bboxes = bboxes

        self._comment = comment

    @property
    def page(self):
        return self.bboxes[0].page

    @property
    def pages_covered(self):
        return set([bbox.page for bbox in self.bboxes])

    @property
    def comment(self):
        if self._comment is not None:
            return self._comment
        else:
            result = u"\n".join([bbox.text for bbox in self.bboxes if bbox.text is not None])
            if result is None:
                return "Empty set of bounding boxes."
            else:
                return result

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if len(self.bboxes) == 0:
            return u"Empty bounding boxes"

        result = u"Bounding boxes:\n"
        for bbox in self.bboxes:
            result += str(bbox)

        if self._comment is not None:
            result += u" with comment:\n%s" % self._comment
        else:
            result += u" without a comment"

        return result

    def __eq__(self, other):
        if not isinstance(other, PDFLocBoundingBoxes):
            return NotImplemented

        if len(self.bboxes) != len(other.bboxes):
            return False

        return all([self.bboxes[i] == other.bboxes[i] for i in range(len(self.bboxes))])

    def __ne__(self, other):
        return not self.__eq__(other)


class BoundingBoxOnPage(object):
    def __init__(self, bbox, page, text=None):
        """
        Represent a bounding box.
        :param tuple|BoundingBox bbox: (x0, y0, x1, y1)
        :param int page:
        :param str text:
        """
        super(BoundingBoxOnPage, self).__init__()

        assert isinstance(bbox, tuple) or isinstance(bbox, BoundingBox)
        assert isinstance(page, int)

        if isinstance(bbox, BoundingBox):
            self.bbox = bbox
        else:
            self.bbox = BoundingBox(
                start=Point(x=bbox[0], y=bbox[1]),
                end=Point(x=bbox[2], y=bbox[3])
            )

        self.page = page
        self.text = text

    def __repr__(self):
        return "Page %i, '%s', %s" % (self.page, str(self.bbox),
                                      self.text.encode("ascii", "ignore") if self.text is not None else "")

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if not isinstance(other, BoundingBoxOnPage):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class BoundingBox(object):
    _start = None
    _end = None

    def __init__(self, start, end):
        super(BoundingBox, self).__init__()

        assert isinstance(start, Point)
        assert isinstance(end, Point)

        self._start = start
        self._end = end

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    def width(self):
        return self.end.x - self.start.x

    def height(self):
        return self.start.y - self.end.y  # y axis is inverted in PDF

    def __str__(self):
        return "Bbox[start=%s, end=%s]" % (self.start, self.end)

    def __eq__(self, other):
        if not isinstance(other, BoundingBox):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, i):
        if i == 0:
            return self.start.x
        elif i == 1:
            return self.start.y
        elif i == 2:
            return self.end.x
        elif i == 3:
            return self.end.y
        elif isinstance(i, slice):
            return [self[ii] for ii in range(*i.indices(len(self)))]
        else:
            raise IndexError()

    def __len__(self):
        return 4


class PointOnPage(object):
    def __init__(self, point, page):
        """
        Represent a point on a page.
        :param tuple|Point point: (x, y)
        :param int page:
        """
        super(PointOnPage, self).__init__()

        assert isinstance(point, tuple) or isinstance(point, Point)
        assert isinstance(page, int)

        if isinstance(point, Point):
            self.point = point
        else:
            self.point = Point(x=point[0], y=point[1])

        self.page = page

    def __repr__(self):
        return "Page %i, '%s'" % (self.page, str(self.point))

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if not isinstance(other, PointOnPage):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


class Point(object):
    _x = 0.0
    _y = 0.0

    def __init__(self, x, y):
        super(Point, self).__init__()

        self._x = x
        self._y = y

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __str__(self):
        return "[%f, %f]" % (self.x, self.y)

    def __eq__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, i):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        else:
            raise IndexError()

    def __len__(self):
        return 2
