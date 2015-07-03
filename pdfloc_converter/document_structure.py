from pdfloc_converter.pdfloc import PDFLoc

__author__ = 'Martin Pecka'

class NavigationTree(object):
    def __init__(self):
        super(NavigationTree, self).__init__()

        self._tree = dict()

    def find_layout_char(self, pdfloc):
        assert isinstance(pdfloc, PDFLoc)
    
        if pdfloc.page not in self._tree:
            raise KeyError(pdfloc.page)
        if pdfloc.keyword_num not in self._tree[pdfloc.page]:
            raise KeyError(pdfloc.keyword_num)
        if pdfloc.string_num >= len(self._tree[pdfloc.page][pdfloc.keyword_num]):
            raise KeyError(pdfloc.string_num)
        if pdfloc.instring_num >= len(self._tree[pdfloc.page][pdfloc.keyword_num][pdfloc.string_num]):
            raise KeyError(pdfloc.instring_num)
    
        return self._tree[pdfloc.page][pdfloc.keyword_num][pdfloc.string_num][pdfloc.instring_num]

    def __contains__(self, item):
        return item in self._tree

    def __getitem__(self, key):
        return self._tree[key]

    def __setitem__(self, key, value):
        self._tree[key] = value

    def __delitem__(self, key):
        del self._tree[key]

    def __iter__(self):
        return iter(self._tree)

    def __len__(self):
        return len(self._tree)