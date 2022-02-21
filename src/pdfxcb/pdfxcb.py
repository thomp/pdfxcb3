import argparse
import imp
import json
import math
import os
import os.path
import re
import shutil
import signal
import sys
import tempfile
import uuid

import logging
import logging.config


# define LG as the generic logger *prior* to loading any
# pdfxcb-specific modules
lg = logging
# and immediately configure the logger format
json_log_format = '%(message)s'
lg.basicConfig(format=json_log_format,stream=sys.stdout)


import pdfxcb.barScan as barScan
import pdfxcb.json1 as json1
import pdfxcb.pdf as pdf


# handle external signals requesting termination
def signal_handler(signal, frame):
    # Ensure receipt of signal is logged prior to terminating
    msg = json1.json_exit_on_external_request_msg()
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit()

signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


#
# function definitions
#
def locate_cover_sheets (png_file_tuples,containing_dir,match_re,scan_region):
    """
    Given the list of files specified by PNG_FILE_TUPLES (a set of
    tuples where the first member of each tuple specifies the name of
    the PNG file) and CONTAINING_DIR, identify those files containing
    a barcode. Return multiple values: a list of the corresponding
    barcodes and a list of the corresponding indices.
    """
    barcodes = []
    indices = []
    # I: index in IMAGE_FILES
    i = 0
    i_max = len(png_file_tuples)
    while (i<i_max):
        # log progress by default (otherwise, this can be a long period of silence...)
        lg.info(
            json1.json_progress(
                f'looking for barcode on {i} of {i_max} PNG files')
            )
        lg.info(containing_dir)
        lg.info(png_file_tuples[i][0])
        image_file_spec = os.path.join(containing_dir,png_file_tuples[i][0])
        lg.debug(image_file_spec)
        maybe_barcode = barScan.barcodeScan(
            image_file_spec,
            scan_region         # None
        )
        # don't ignore barcode if consider is true
        consider = True
        if maybe_barcode:
            if match_re:
                consider = match_re.match(maybe_barcode)
            if consider:
                barcodes.append(maybe_barcode)
                indices.append(i)
        i = i+1
        #lg.debug(barcodes)
        #lg.debug(indices)
    return barcodes,indices

def executable_sanity_checks (executables):
    """
    Check for availability of executables specified in the list of
    strings EXECUTABLES.
    """
    for executable_spec in executables:
        if not shutil.which(executable_spec):
            msg = json1.json_msg_executable_not_accessible(executable_spec)
            lg.error(msg)
            lg.info(json1.json_last_log_msg())
            sys.exit(msg)

def generate_output_file_names(cover_sheet_barcodes,
                               cover_sheet_indices,
                               output_dir):
    file_names = []
    for cover_sheet_barcode,cover_sheet_index in zip(cover_sheet_barcodes,cover_sheet_indices):
        cover_sheet_index_as_string = str.format("{0:0>03d}", cover_sheet_index)
        version = -1
        # sanity check on version (completely arbitrary at this point)
        max_version = 99
        while (not version >= max_version and
               (version < 0 or os.path.exists(path))):
            version = version + 1
            file_name = f'{cover_sheet_barcode}-{cover_sheet_index_as_string}-{version}.pdf'
            path = os.path.join(output_dir,file_name)
        file_names.append(path)
    return file_names

def generate_output_file_names_split_after(page_ranges,output_dir):
    file_names = []
    for page_range in page_ranges:
        page_range_as_string = str.format("{0:0>03d}", page_range[0]) + "-"+str.format("{0:0>03d}",page_range[1])
        version = -1
        # sanity check on version (completely arbitrary at this point)
        max_version = 99
        while (not version >= max_version and
               (version < 0 or os.path.exists(path))):
            version = version + 1
            file_name = f'{page_range_as_string}-{version}.pdf'
            path = os.path.join(output_dir,file_name)
        file_names.append(path)
    return file_names

def generate_page_ranges(cover_sheet_indices,
                         png_file_page_number_tuples,
                         number_of_pages):
    """
    Return a list of tuples. COVER_SHEET_INDICES is an array of
    integers, each an index value identifying a member of
    PNG_FILE_PAGE_NUMBER_TUPLES which corresponds to a cover sheet.
    See INVOKE_PDFIMAGES_ON docstring for more on
    PNG_FILE_PAGE_NUMBER_TUPLES. Calling code must guarantee that
    tuples in PNG_FILE_PAGE_NUMBER_TUPLES are ordered (ascending) with
    respect to page numbers.
    """
    # to capture last set of pages, tag on an imaginary cover sheet at the end
    cover_sheet_indices.append(
        len(png_file_page_number_tuples)
    )
    png_file_page_number_tuples.append((None,number_of_pages+1))
    page_ranges = []
    for cover_sheet_index, next_cover_sheet_index in zip(cover_sheet_indices[:-1],cover_sheet_indices[1:]):
        page_ranges.append(
            (png_file_page_number_tuples[cover_sheet_index][1],
             png_file_page_number_tuples[next_cover_sheet_index][1]-1))
    return page_ranges

def generate_page_ranges_split_after(split_after,number_of_pages):
    """
    Return a list of tuples.
    """
    number_of_docs = int(math.ceil(number_of_pages/split_after))
    page_ranges = [(n*split_after-(split_after-1),n*split_after) for n in range(1,number_of_docs+1)]
    # adjust the last tuple since the number of pages may not be a
    # multiple of SPLIT_AFTER (the last set of pages may be smaller
    # than split_after pages)
    last_tuple = page_ranges[len(page_ranges)-1]
    page_ranges[len(page_ranges)-1] = (last_tuple[0],number_of_pages)
    return page_ranges

def pdfxcb_sanity_checks (output_dir,pdf_file_spec,rasterize_p,region):
    # file and dir sanity checks
    if (not output_dir):
        sys.exit("The output directory must be specified.")
    directory_sanity_checks ([output_dir],True)
    file_sanity_checks ([pdf_file_spec],True)
    # region/rasterize sanity check
    if (not rasterize_p and region):
        sys.exit("If REGION is specified, then RASTERIZE_P should be true.")
    # executables sanity check
    required_executables = [
        'gs'
        #'pdftoppm'
    ]
    executable_sanity_checks(required_executables)
    required_modules = [
        'PyPDF2'
        #'cv2'
    ]
    module_sanity_checks (required_modules,True)

def file_and_dir_sanity_checks (dirs,files):
    directory_sanity_checks (dirs,True)
    file_sanity_checks (files,True)

def pdfxcb (pdf_file_spec,output_dir,match_re,rasterize_p,region,
            clean_up_png_files_p=True
            ):
    """
    Given the file specified by PDF_FILE_SPEC, look for cover sheets
    and split the PDF at each coversheet. Name output file(s) based on
    cover sheet content. Write files to directory specified by
    OUTPUT_DIR. Return True. If MATCH_RE is defined, ignore barcodes
    unless the corresponding string matches the regex MATCH_RE. Use
    RASTERIZE_P = False if the PDF does not contain vector graphics
    but is solely bitmap data (e.g., the PDF was generated from a
    scanned document). If REGION has the form [ float1, float2,
    float3, float4 ], use the region specified by REGION when scanning
    for a barcode or other indicator of a cover sheet.
    """
    global lg
    pdfxcb_sanity_checks(output_dir,pdf_file_spec,rasterize_p,region)
    # If confident that the PDF under analysis is derived from a scan
    # (i.e., contains only bitmap data), then the images embedded in
    # the PDF can be analyzed directly. If the PDF may contain vector
    # data on the cover sheet pages, then rasterization is indicated.
    # See doc/optimization.md for notes on time implications.

    # PNG_FILE_PAGE_NUMBER_TUPLES is an array where each member has
    # the form (<PNG file name>, <PDF page number>). There is no
    # guarantee that all pages in the original PDF document are
    # represented. Furthermore, there may be multiple PNG images per
    # PDF page -- i.e., the array might include ("flurpies.png",1) and
    # ("glurpies.png",1).

    # FIXME: consider having a single call here -- FOO -- that specializes on rasterize_p
    if rasterize_p:
        # extract PDF pages as image data (PNG files)
        png_file_page_number_tuples = split_pdf_to_png_files(pdf_file_spec,output_dir)
        # Once rasterized pages are generated, optionally scan for cue marks
        # CUE_INDICES = array where each member is an integer indicating index of member of png_file_page_number_tuples where the corresponding bitmap has a cue mark
        # cue_indices = scan_for_cue_marks(png_file_page_number_tuples) <-- use urh_corner_mean w/reasonable threshold (10? 20? 50?) for "black"
    else:
        # extract images directly from PDF
        png_file_page_number_tuples = invoke_pdfimages_on(pdf_file_spec,output_dir)
    # Code below expects png_file_page_number_tuples to be ordered with respect to page number.
    # Note that sorted default is ascending order.
    png_file_page_number_tuples = sorted(png_file_page_number_tuples,
                                         key=lambda tuple: tuple[1])
    #
    # locate cover sheets
    #
    lg.info("Locating cover sheets")
    if rasterize_p:
        # possibilities:
        # 1. png files represent rasterized pages
        if region:
            scan_region = region
        else:
            scan_region = ([0,0,0.7,0.5])
    else:
        # 2. png files represent images from PDF (via pdfimages)
        scan_region = None # None is not treated as the equivalent of ([0,0,1,1]). ([0,0,1,1]) triggers cropping by barcodeScan.
    cover_sheet_barcodes, cover_sheet_indices = locate_cover_sheets(png_file_page_number_tuples,output_dir,match_re,scan_region)
    print(cover_sheet_barcodes)
    if clean_up_png_files_p:
        for png_file_tuple in png_file_page_number_tuples:
            os.remove(os.path.join(output_dir,png_file_tuple[0]))
    pdf_length = pdf.pdf_number_of_pages(pdf_file_spec)
    page_ranges = generate_page_ranges(cover_sheet_indices,
                                       png_file_page_number_tuples,
                                       pdf_length)
    output_file_names = generate_output_file_names(cover_sheet_barcodes,
                                                   cover_sheet_indices,
                                                   output_dir)
    pdf.pdf_split(pdf_file_spec,output_file_names,page_ranges)
    lg.info(json1.json_msg(40,
             ['Analysis and burst completed'],
             False,
             files=output_file_names,
             data={
                 'barcodes': cover_sheet_barcodes,
                 'indices': cover_sheet_indices
             }
    ))
    return True

def pdfxcb_split_after (pdf_file_spec,output_dir,split_after_n_pp):
    """
    Given the file specified by PDF_FILE_SPEC, split the PDF after
    every SPLIT_AFTER pages. Name output file(s) based page ranges.
    Write files to directory specified by OUTPUT_DIR. Return True.
    """
    global lg
    file_and_dir_sanity_checks([output_dir],[pdf_file_spec])
    pdf_length = pdf.pdf_number_of_pages(pdf_file_spec)
    page_ranges = generate_page_ranges_split_after(split_after_n_pp,
                                                   pdf_length)
    output_file_names = generate_output_file_names_split_after(page_ranges,
                                                               output_dir)
    pdf.pdf_split(pdf_file_spec,output_file_names,page_ranges)
    lg.info(json1.json_msg(40,
             ['Analysis and burst completed'],
             False,
             files=output_file_names,
             data={
                 #'barcodes': cover_sheet_barcodes,
                 #'indices': cover_sheet_indices
             }
    ))
    return True

def directory_sanity_check (directory_spec,exitp):
    if not os.path.isdir(directory_spec):
        lg.error(json1.json_file_not_found(directory_spec))
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit("Directory " + directory_spec + " not found.")

def directory_sanity_checks (directories,exitp):
    for directory_spec in directories:
        directory_sanity_check(directory_spec,True)

def file_sanity_check (file,exitp):
    if not os.path.isfile(file):
        lg.error(json1.json_file_not_found(file))
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit("File " + file + " not found.")

def file_sanity_checks (files,exitp):
    for file in files:
        file_sanity_check(file,True)

def invoke_pdfimages_on (pdf_file_spec,output_dir):
    """
    Extract images in PDF file specified by PDF_FILE_SPEC into a
    series of files, each representing a single PNG image. Write files
    to directory specified by OUTPUT_DIR.

    Returns a list of tuples where each tuple has the structure
    (png_file,png_file_page_number) where png_file is a string representing the file name and png_file_page_number is an
    integer. The list is an ordered sequence with respect to page
    number - low to high.
    """
    png_file_page_number_tuples = None
    try:
        # sanity check
        if not os.path.isabs(pdf_file_spec):
            msg = "The input PDF must be specified as an absolute file path"
            lg.error(json1.json_msg(108,[msg],False,files=[pdf_file_spec]))
            sys.exit(msg)
        else:
            lg.info("png_file_page_number_tuples 0")
            png_file_page_number_tuples = pdf.pdfimages(pdf_file_spec,
                                                        output_dir)
    except Exception as e:
        lg.debug(str(e))
        msg = json1.json_failed_to_convert_pdf(e,pdf_file_spec)
        lg.error(msg)
        lg.info(json1.json_last_log_msg())
        sys.exit(msg)
    else:
        lg.info(json1.json_pdf_to_pngs_success(pdf_file_spec,
                                               None #png_files
        ))
        return png_file_page_number_tuples

def module_sanity_checks (module_names,exitp):
    """MODULE_NAMES is a sequence of strings"""
    for module_name in module_names:
        module_sanity_check (module_name,exitp)

def module_sanity_check (module_name,exitp):
    """MODULE_NAME is a string"""
    try:
        imp.find_module(module_name)
    except ImportError:
        msg = json1.json_msg_module_not_accessible(module_name)
        lg.error(msg)
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit(msg)

def split_pdf_to_png_files (pdf_file_spec,output_dir):
    """
    Split the PDF file specified by PDF_FILE_SPEC into a series of
    files, each representing a single page as a PNG image. Write files
    to the directory specified by OUTPUT_DIR.

    Return a list of tuples where the first member of each tuple is a
    string representing the file name and the second member of each
    tuple is the corresponding page number (page numbering begins at
    1).
    """
    png_files = None
    try:
        # sanity check
        if not os.path.isabs(pdf_file_spec):
            msg = "The input PDF must be specified as an absolute file path"
            lg.error(json1.json_msg(108,[msg],False,files=[pdf_file_spec]))
            sys.exit(msg)
        else:
            # array of (<file_name>,<page_number>) tuples
            png_specs = pdf.pdf_to_pngs(pdf_file_spec,output_dir)
    except Exception as e:
        msg = json1.json_failed_to_convert_pdf(e,pdf_file_spec)
        lg.error(msg)
        print("failed to convert PDF file(s): %s" % pdf_file_spec)
        print("e: %s" % e)
        lg.info(json1.json_last_log_msg())
        sys.exit(msg)
    else:
        lg.info(json1.json_pdf_to_pngs_success(pdf_file_spec,png_specs))
        return png_specs

def write_page_scores(page_scores, output_file):
    f = open(output_file, 'w')
    for page in page_scores:
        for row in page:
            for datum in row:
                f.write(str(datum))
                f.write(' ')
            f.write('\n')
        f.write('\n')
    f.close()

def write_paths(paths, output_file):
    f = open(output_file, 'w')
    for path in paths:
        f.write(path)
        f.write('\n')
    f.close()

def main():
    """Handle command-line invocation of pdfxcb.py."""
    global lg
    parser = argparse.ArgumentParser(description="This is pdfxcb")
    # Split after every Nth page. If N is 3, split into pp 1-3, 4-6, 7-9, etc.
    parser.add_argument("-e",
                        help="A whole number. If specified, split after every Nth page, ignoring -m and -r.",
                        action="store",
                        default=0,
                        dest="split_after_n_pp",
                        type=int
                        )
    parser.add_argument("-f",
                        # FIXME: "busca.log" shouldn't be hardcoded -- set up a default_log_path var to handle this
                        help="Absolute path to log file. If not specified, logs to busca.log.",
                        action="store",
                        dest="log_file",
                        type=str)
    # FIXME: is this mandatory? If so, this should be explicit.
    parser.add_argument("-d",
                        help="absolute path to output directory",
                        action="store",
                        dest="output_dir",
                        type=str)
    parser.add_argument("-m",
                        help="match barcodes to regex (ignore if no match)",
                        action="store",
                        dest="match_re_string",
                        type=str)
    parser.add_argument("-p",
                        help="identifier for a specific instance of pdfxcb",
                        action="store",
                        dest="identifier",
                        type=str)
    # These four values correspond to scan_region = ([0,0,0.7,0.5])
    parser.add_argument("-r",
                        help="specify region of the page to be evaluated",
                        action="store",
                        dest="region",
                        nargs=4,
                        type=float)
    parser.add_argument("-l",
                        help="integer between 0 (verbose) and 51 (terse) defining logging",
                        action="store",
                        dest="log_level",
                        type=int)
    # https://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
    parser.add_argument('-v', '--version', action='version', version="0.0.3")
    parser.add_argument('--debug',
                        help="do not clean up files used during processing"
                        )
    parser.add_argument("input_files", help="one or more input (PDF) files",
                        # keep nargs as we may want to accept multiple PDFs as input at some point
                        nargs=1,
                        type=str)
    args = parser.parse_args()
    #
    # define logging (level, file, message format, ...)
    #
    log_level = args.log_level
    if isinstance(log_level, int) and log_level >= 0 and log_level <= 51:
        log_level = log_level
    else:
        # since this function doesn't necessarily exit quickly
        log_level = logging.INFO
    if args.log_file:
        logfile = args.log_file
    else:
        logfile = 'busca.log'
    json_log_format = '%(message)s'
    for handler in lg.getLogger().handlers:
        lg.getLogger().removeHandler(handler)
    formatter = logging.Formatter(json_log_format)
    # sanity check for existence of log file directory
    if (os.path.dirname(logfile) and
        not os.path.exists(os.path.dirname(logfile))):
        raise Exception(str.format("log file directory {0} not present",
                                   os.path.dirname(logfile)))
    file_handler = logging.FileHandler(logfile,'w')
    file_handler.setFormatter(formatter)
    lg.getLogger().addHandler(file_handler)
    lg.getLogger().setLevel(log_level)
    if args.identifier:
        identifier = args.identifier
    else:
        identifier = str(uuid.uuid1())
    rasterize_p = False
    if args.region:
        region = args.region
        rasterize_p = True  # if region is specified, rasterize_p should be true
        # lg.debug("args.region: %s", args.region)
    else:
        region = None
    # 1000[0-9][0-9][0-9]$ matches on tt user id
    match_re_string = args.match_re_string
    lg.debug(match_re_string)
    match_re = None
    if match_re_string:
        match_re = re.compile(match_re_string)
    pdf_file_spec = args.input_files[0]
    lg.debug(pdf_file_spec)
    lg.info(json1.json_first_log_msg(identifier, files = [pdf_file_spec] ))
    # generic debugging
    lg.debug(os.getcwd())         # current/working directory
    # might also want to import platform to get architecture, other details...
    if (args.split_after_n_pp > 0):
        pdfxcb_split_after(pdf_file_spec,args.output_dir,args.split_after_n_pp)
    else:
        try:
            pdfxcb(pdf_file_spec,
                   args.output_dir,
                   match_re,
                   rasterize_p,
                   region,
                   not args.debug #clean_up_png_files_p
                   )
        except Exception as e:
            lg.error("Crash and burn")
            lg.error(sys.exc_info()[0])
            raise
        lg.info(json1.json_last_log_msg())

if __name__ == "__main__":
    main()
