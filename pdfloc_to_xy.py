#!/usr/bin/env python
import os
import sys
import argparse
from collections import deque

from pdfloc_converter.converter import PDFLocConverter
from pdfloc_converter.pdfloc import PDFLocPair, BoundingBoxOnPage, PDFLocBoundingBoxes
from pdfloc_converter.utils.paraformatter import ParagraphFormatter


class PDFLocConverterCLI(object):
    def parse_pdfloc_or_bounding_box_from_string(self, string):
        string = string.strip()
        if string.startswith("#pdfloc"):
            (start, end) = tuple(string.split(";", 1))
            start = start.strip()  # strip whitespace

            end = end.strip()  # strip whitespace
            parts = end.split(" ", 1)  # allow comments separated by a space at the end of the pdfloc
            end = parts[0]

            comment = parts[1] if len(parts) > 1 else None

            return PDFLocPair(start, end, comment)
        else:
            bboxes = []
            for bbox in string.split(";"):
                (page, left, top, right, bottom) = bbox.split(",")
                page = int(page)
                left = float(left)
                top = float(top)
                right = float(right)
                bottom = float(bottom)
                bboxes.append(BoundingBoxOnPage((left, top, right, bottom), page))
            return PDFLocBoundingBoxes(bboxes)

    # Process the command-line instructions.
    def execute_commandline(self, argv):
        # get rid of argv[0], since it only contains the command that was run
        args = self.parse_commandline(argv[1:])

        jobs = deque([])
        for job in args.jobs:
            jobs.append(self.parse_pdfloc_or_bounding_box_from_string(job))

        pdfloc_jobs = [job for job in jobs if isinstance(job, PDFLocPair)]
        bbox_jobs = [job for job in jobs if isinstance(job, PDFLocBoundingBoxes)]

        # if we have an input jobs file, we parse the whole document in advance
        pdflocs = pdfloc_jobs if args.jobs_file is None else []
        bboxes = bbox_jobs if args.jobs_file is None else []

        converter = PDFLocConverter(args.filename, pdflocs, bboxes)
        converter.parse_document()

        pages = converter._pdf_document.catalog['Pages'].resolve()['Kids']

        max_pdf_object_num = 0
        for xref in converter._pdf_document.xrefs:
            max_pdf_object_num = max(max_pdf_object_num, max(xref.offsets.keys()))

        pdf_update_string = u'\n'

        bboxes_result = {}

        # process all jobs, writing their results to stdout
        while True:
            # read more jobs from the input job file if specified and all command-line jobs have been processed
            if len(jobs) == 0 and args.jobs_file is not None and not args.jobs_file.closed:
                stop = False
                while not stop:
                    lines = []
                    while True:  # read lines until empty line or line containing semicolon
                        line = args.jobs_file.readline()
                        if line is None or line == "":
                            args.jobs_file.close()
                            stop = True
                            break
                        if line == "\n":
                            break
                        lines.append(line.strip())
                        if line.find(";") > -1:
                            break
                    if len(lines) > 0:
                        # if we read something, try to parse it as pdfloc or boundingbox
                        try:
                            job = ";".join(lines)
                            jobs.append(self.parse_pdfloc_or_bounding_box_from_string(job))
                            break  # let the loop process the parsed job before we read further
                        except ValueError as e:
                            print "Error parsing %s. Cause: %s" % (job, str(e))
                            break

            if len(jobs) == 0:
                # quit the loop when there are really no more jobs to be done
                break

            job = jobs.popleft()

            try:
                if isinstance(job, PDFLocPair):
                    bboxes = PDFLocBoundingBoxes(converter.pdfloc_pair_to_bboxes(job), job.start.page, job.comment)
                    if bboxes.page not in bboxes_result:
                        bboxes_result[bboxes.page] = []
                    bboxes_result[bboxes.page].append(bboxes)
                    #print "\n".join([str(bbox).strip() for bbox in bboxes.bboxes]) + "\n\n"
                else:
                    pdfloc_pair = converter.bboxes_to_pdfloc_pair(job)
                    #print str(pdfloc_pair) + "\n\n"
            except KeyError as e:
                print "Error converting %s. Cause: %s" % (job, repr(e))

        previous_startxref = 515742  # TODO
        orig_pdf_size = os.path.getsize(args.filename.name)-1
        xref_table = u"xref\n0 1\n0000000000 65535 f \n"

        for page_num in bboxes_result.keys():
            bbox_list = bboxes_result[page_num]
            page_ref = converter._pdf_document.catalog['Pages'].resolve()['Kids'][page_num-1]
            page = page_ref.resolve()

            xref_table += u"%d 1\n%010d 00000 n \n" % (page_ref.objid, len(pdf_update_string)+orig_pdf_size)

            annots_objid = max_pdf_object_num + 1
            max_pdf_object_num += 1

            exiting_annots_objids = []
            if 'Annots' in page:
                exiting_annots = page['Annots']
                exiting_annots_objids = [annot.objid for annot in page['Annots']]

            pdf_update_string += u"%i 0 obj\n<<" \
                                 u"/Type/Page" \
                                 u"/Parent %i 0 R " \
                                 u"/Resources %i 0 R" \
                                 u"/MediaBox [%i %i %i %i]" \
                                 u"/Group<</S/Transparency/CS/DeviceRGB/I true>>" \
                                 u"/Contents %i 0 R" \
                                 u"/Annots %d 0 R" \
                                 u">>\nendobj\n" % (page_ref.objid, page['Parent'].objid, page['Resources'].objid,
                                         page['MediaBox'][0], page['MediaBox'][1], page['MediaBox'][2], page['MediaBox'][3],
                                         page['Contents'].objid, annots_objid)

            annots = range(max_pdf_object_num + 1, max_pdf_object_num + 1 + len(bbox_list))
            max_pdf_object_num += len(bbox_list)

            xref_table += u"%d 1\n%010d 00000 n \n" % (annots_objid, len(pdf_update_string) + orig_pdf_size)

            items_refs = u" 0 R ".join(str(objid) for objid in exiting_annots_objids + annots) + u" 0 R"
            pdf_update_string += u"%d 0 obj [%s] endobj\n" % (annots_objid, items_refs)

            i = 0
            for annotation_bboxes in bbox_list:
                objid = annots[i]

                xref_table += u"%d 1\n%010d 00000 n \n" % (objid, len(pdf_update_string) + orig_pdf_size)

                comment = annotation_bboxes.comment.decode('utf-8').replace(u")", u"\\)")
                first_box = annotation_bboxes.bboxes[0].bbox
                last_box = annotation_bboxes.bboxes[-1].bbox

                pdf_update_string += u"%d 0 obj\n<<" \
                                     u"/Subtype /Highlight" \
                                     u"/P %d 0 R" \
                                     u"/C [1 1 0]" \
                                     u"/F 4" \
                                     u"/Contents (%s)" \
                                     u"/Rect [%d %d %d %d] " \
                                     u"/QuadPoints [" % (
                    objid, page_ref.objid, comment,
                    min(first_box[0], last_box[0]), min(first_box[1], last_box[1]),
                    max(first_box[2], last_box[2]), max(first_box[3], last_box[3])
                )

                j = 0
                for bbox in annotation_bboxes.bboxes:
                    bbox = bbox.bbox

                    top = min(bbox[1], bbox[3])
                    bottom = max (bbox[1], bbox[3])
                    left = min(bbox[0], bbox[2])
                    right = max(bbox[0], bbox[2])
                    if top - bottom > 20:
                        top = bottom + 20

                    pdf_update_string += u"%d %d %d %d %d %d %d %d " % (
                        left, bottom, right, bottom, left, top, right, top
                    )

                    j += 1

                pdf_update_string += u"]>>\nendobj\n"
                i += 1

        pdf_update_string += u"\n"

        xref_position = orig_pdf_size + len(pdf_update_string)

        pdf_update_string = pdf_update_string + xref_table + u"\n" \
                                                             u"trailer\n<<\n/Size %d /Root %d 0 R /Prev %d\n>>\n" % \
                                                             (max_pdf_object_num+1, converter._pdf_document.xrefs[0].trailer['Root'].objid, previous_startxref)

        pdf_update_string += u"startxref\n%d\n%%%%EOF" % xref_position
        print pdf_update_string

        return 0

    def parse_commandline(self, argv):
        help_description = '''Performs conversions between #pdfloc(...) and\
bounding box PDF area specifiers. First, a PDF file is needed, which is parsed and prepared for\
running the conversions. After that, you specify the "jobs" - either pdflocs or bounding boxes that need\
to be converted to the other type (you can mix both job types together in one call).

The format of a pdfloc job is:
    #pdfloc(abcd,1,1,1,1,1,1,1);#pdfloc(abcd,1,1,2,1,1,1,1) optional comment separated by a space

The format of bounding boxes job is:
    1,0,0,200,200;1,0,5,200,205;...

    You can separate bounding boxes using newline instead of semicolon.
    In such case, everything up to the next empty line is considered a part of this job.
    It is sufficient to provide only the first and last bounding box from the set covering the whole area.
'''
        parser = argparse.ArgumentParser(description=help_description, formatter_class=ParagraphFormatter)

        parser.add_argument("-f", "--jobs-file", type=argparse.FileType(mode='r'),
                            help="A file containing the conversion jobs to be done. "
                                 "Can be stdin (specify '-' (just a dash) as the filename).")

        parser.add_argument("filename", type=argparse.FileType(mode='rb'),
                            help="The file to do conversions within.")

        parser.add_argument("jobs", nargs="*", help="The list of jobs to convert.")

        return parser.parse_args(argv)


if __name__ == '__main__':
    cli = PDFLocConverterCLI()
    sys.exit(cli.execute_commandline(sys.argv))
