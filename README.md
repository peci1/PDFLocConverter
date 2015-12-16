PDFLoc Converter
================

*PDFLoc Converter* is an experimental Python library and utility to convert between Adobe's unpublished, but widely used **#pdfloc(...)** *PDF location* specifiers, and a list of bounding boxes.
  
This format is usually used by ebook readers (both harware and software) that utilize the Adobe Reader Mobile SDK (RMSDK) for handling PDF files.
Adobe provides no free tool to parse or use these PDF location markers.
This library tries to provide such a tool based on the free software [pdfminer](https://euske.github.io/pdfminer/).

\#pdfloc format
--------------

The format of a pdfloc is the following: `#pdfloc(89ab,1,12,2,4,0,0,1)`. 
The purpose of a pdfloc is to precisely refer to the position of a character.
The use can be two-fold - specifying the start/end-point of a highlight, or positioning some markers aligned with text.

The meaning of the numbers in a pdfloc is not described anywhere officialy. 
The author asked Adobe to provide a description, but no money, no success.
So the following semantics description is only a best guess which was verified on a bunch of files.
If you have some more ideas on the still unclear things or if you just have a pdfloc that doesn't work according to the described algorithm, please, raise an issue here on Github.

**To understand the following description, the reader is required to know [some internals of the PDF format](http://partners.adobe.com/public/developer/en/pdf/PDFReference.pdf) (mainly to know there are some objects and operators /Sections 2.1.2 and 3/).**

Let us first name the elements in a pdfloc:

`#pdfloc(hash, page, keyword_num, string_num, instring_num, flag1, is_up_to_end, is_not_up_to_end)`

- **hash**: 4 hexadecimal digits that serve as a hash of the corresponding PDF document.
            *PDFLoc Converter* ignores this value (although it could check if you're not trying to apply a pdfloc to a wrong document - this check is left up to the end user).
- **page**: Page number. Indexed from 0.
- **keyword\_num**: Position of the corresponding **Tj** (*show text string*) or **TJ** (*show more text strings*) operator in the content of the PDF object corresponding to the page (each page has one main content object related to it).
                   Indexed from 0.  
                   To get the correct position, you count **all keywords** in the stream **except** *m*, *l*, *c*, *v*, *y*, *h*, *re* and *n*.
                   I guess these are ignored in the counts because they do not alter the position of the text in any way (they are related to curves/rectangles).
                   But e.g. the color changing commands like *rg* are counted.                   
                   On the other hand, you need to resolve all *Do* directives (they act as *includes* for subparts of a page, like figures and images).
- **string\_num**: The *TJ* keyword has an *array* of *PDF strings* (either literal strings /denoted by parentheses/ or hexadecimal strings /denoted by angle brackets/) associated with it.
                  This is the position of the *PDF string* in the associated *array*.
                  Indexed from 0.  
                  The *array* may also contain positioning information besides *PDF strings*.
                  They are (mostly negative) numbers and they are ignored when counting.
- **instring\_num**: Each *PDF string* contains several characters.
                     This is the position of the character in the corresponding *PDF string*.
                     Indexed from 0.  
                     The final position is the top left corner of this character.
                     So if this pdfloc denotes the end of a highlight, it usually points one character "further" than the higlight should be.
                     To highlight whole line, the end marker has to point to the beginning of the following line.
                     If there is no following line, see *is\_up\_to\_end*.
- **flag1**: The meaning of this is unknown. It is most probably a binary flag.
- **is\_up\_to\_end**: Using just the previously described, we wouldn't be able to mark a highlight *up to the end of a PDF object*.
                       If you want to denote such a position, this flag is set to 1, and all of *keyword\_num*, *string\_num* and *instring\_num* have a special value **E** (not a number, just *E*).
- **is\_not\_up\_to\_end**: This just seems to be a negation of the previous flag. Odd.
                            Any ideas welcome.

Example PDF page object
-----------------------

To better understand the definition above, let's have a look at the following excerpt from a PDF page content object.
When reading it, keep in mind that the PDF is executed by a [stack-machine](https://en.wikipedia.org/wiki/Stack_machine), or, said differently, it uses [postfix notation](https://en.wikipedia.org/wiki/Reverse_Polish_notation).
This effectively means all arguments precede the operator.
On each line, everything after a # is a comment. 

    <object id="167">
    0 g 0 G                         # count the 1-arg g and G operators
    0 g 0 G                         # count the g and G operators
    0 g 0 G                         # count the g and G operators
    1 0 0 1 52.446 643.973 cm       # count the 6-arg cm operator
    q                               # count the arg-less q operator
    0.1567 0 0 0.1567 0 0 cm        # count the 6-arg cm operator
    q                               # count the arg-less q operator
    1 0 0 1 0 0 cm                  # count the 6-arg cm operator
    /Im5 Do                         # here, we need to include XObject named Im5; skipped here
    Q                               # count the arg-less Q operator
    Q                               # count the arg-less Q operator
    1 0 0 1 -52.446 -643.973 cm     # count the 6-arg cm operator
    BT                              # count the arg-less BT operator
    # on the following line, some text is finally defined; count all the Tf, Td and TJ operators
    # the first TJ operator has as argument a 17-element array, of which 9 are PDF strings
    # so, if we wanted to refer to the "u" character from the "func-" string, the following would apply:
    #    keyword_num = 18 (0-based count of operators up to the first TJ; assuming the Do operator adds no more operators)
    #    string_num = 8 (0-based count of PDF strings)
    #    instring_num = 1 (0-based index of the character inside the array)
    #    is_up_to_end = 0, is_not_up_to_end = 1    
    /F58 7.9701 Tf 48.959 632.018 Td [(\050a\051)-455(T)80(ypical)-422(learning)-423(curv)15(e)-422(as)-423(a)-422(func-)]TJ 0 -8.966 Td [(tion)-350(of)-350(training)-350(iterations.)]TJ
    ET                              # count the arg-less ET operator
    1 0 0 1 179.79 643.973 cm       # count the 6-arg cm operator
    q                               # count the arg-less q operator
    </object>
    
Further processing
------------------
    
### Pixel position from character ###

Once we know the position of the character refered to, we want to find out the pixel coordinates of its top left corner.
This is achieved by *rendering* the page, and *PDFLoc Converter* utilizes the tool *pdfminer* for that.
So, basically, if *pdfminer* can't correctly render a document, *PDFLoc Converter* will also fail.
The position returned by *PDFLoc Converter* is in the PDF page's units, which are defined by its **MediaBox** (which you can query *pdfminer* for).

### Highlight boxes from start and end positions ###

So we have a pixel position of the start and end of a highlight.
How do we get the set of boxes to be highlighted?

This is not that trivial as it could seem. As long as the start and end is on the same line, everything's easy.
But if you have to span the highlight multiple lines, or columns, or even pages (not sure if pdfloc allows for this), then there has to be some more processing.
Currently, *PDFLoc Converter* uses a heuristic algorithm from *pdfminer* for determining what text block follows after which, and it also uses *pdfminer* to retrieve the line height.

Usage
-----

### Command-line ###

### Python ###

Installation
------------

1. [Install pdfminer](https://euske.github.io/pdfminer/#install).