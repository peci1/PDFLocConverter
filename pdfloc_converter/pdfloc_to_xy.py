#!/usr/bin/env python
import sys
import argparse
from collections import deque

from pdfloc_converter.converter import PDFLocConverter
from pdfloc_converter.pdfloc import PDFLocPair, BoundingBoxOnPage, PDFLocBoundingBoxes


def parse_pdfloc_or_bounding_box_from_string(string):
    string = string.strip()
    if string.startswith("#pdfloc"):
        (start, end) = tuple(string.split(";"))
        return PDFLocPair(start, end)
    else:
        bboxes = []
        for bbox in string.split(";"):
            (page, left, top, right, bottom) = bbox.split(",")
            bboxes.append(BoundingBoxOnPage((left, top, right, bottom), page))
        return PDFLocBoundingBoxes(bboxes)

# Process the command-line instructions.
def main(argv):
    # get rid of argv[0], since it only contains the command that was run
    args = parse_commandline(argv[1:])

    jobs = deque([])
    for job in args.jobs:
        jobs.append(parse_pdfloc_or_bounding_box_from_string(job))

    pdfloc_jobs = [job for job in jobs if isinstance(job, PDFLocPair)]
    bbox_jobs = [job for job in jobs if isinstance(job, PDFLocBoundingBoxes)]

    # if we have an input jobs file, we parse the whole document in advance
    pdflocs = pdfloc_jobs if args.jobs_file is None else []
    bboxes = bbox_jobs if args.jobs_file is None else []

    converter = PDFLocConverter(args.filename, pdflocs, bboxes)
    converter.parse_document()

    # process all jobs, writing their results to stdout
    while len(jobs) > 0:
        job = jobs.popleft()

        try:
            if isinstance(job, PDFLocPair):
                bboxes = converter.pdfloc_pair_to_bboxes(job)
                print "\n".join([str(bbox).strip() for bbox in bboxes]) + "\n\n"
            else:
                pdfloc_pair = converter.bboxes_to_pdfloc_pair(job)
                print str(pdfloc_pair) + "\n\n"
        except KeyError as e:
            print "Error converting %s. Cause: %s" % (job, repr(e))

        # read more jobs from the input job file if specified
        if len(jobs) == 0 and args.jobs_file is not None and not args.jobs_file.closed:
            while True:
                lines = []
                while True:  # read lines until empty line or line containing semicolon
                    line = args.jobs_file.readline()
                    if line is None or line == "":
                        args.jobs_file.close()
                        return 0
                    if line == "\n":
                        break
                    lines.append(line.strip())
                    if line.find(";") > -1:
                        break
                if len(lines) > 0:
                    # if we read something, try to parse it as pdfloc or boundingbox
                    try:
                        job = ";".join(lines)
                        jobs.append(parse_pdfloc_or_bounding_box_from_string(job))
                        break  # let the loop process the parsed job before we read further
                    except ValueError as e:
                        print "Error parsing %s. Cause: %s" % (job, str(e))

    return 0


def parse_commandline(argv):
    parser = argparse.ArgumentParser(description="""Performs conversions between #pdfloc(...) and
bounding box PDF area specifiers. First, a PDF file is needed, which is parsed and prepared for
running the conversions. After that, you specify the "jobs" - either pdflocs or bounding boxes that need
to be converted to the other type (you can mix them together in one call).

The format of a pdfloc area is: #pdfloc(abcd,1,1,1,1,1,1,1,1);#pdfloc(abcd,1,1,2,1,1,1,1,1)
The format of bounding boxes is: 1,0,0,200,200;1,0,5,200,205;...
    At least two bounding boxes are required. You can separate them using newline instead of semicolon.
    In such case, everything up to the next empty line is considered a part of this job.
    It is sufficient to provide only the first and last bounding box from the set covering the whole area.

""")

    parser.add_argument("-f", "--jobs-file", type=argparse.FileType(mode='r'),
                        help="A file containing the conversion jobs to be done. "
                             "Can be stdin (specify '-' (just a dash) as the filename).")

    parser.add_argument("filename", type=argparse.FileType(mode='rb'),
                        help="The file to do conversions within.")

    parser.add_argument("jobs", nargs="*", help="The list of jobs to convert.")

    return parser.parse_args(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
