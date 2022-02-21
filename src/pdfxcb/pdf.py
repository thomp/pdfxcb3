import io
import os
import pathlib
import re
import subprocess
import PyPDF2

import logging

#import pdfxcb.json1
import pdfxcb.json1 as json1


lg=logging


def pdf_number_of_pages(pdf_file):
    """
    Determine the number of pages in a PDF document. Return an integer.
    """
    pdf_path = pathlib.Path(pdf_file)
    with open(pdf_path,"rb") as f:
        reader = PyPDF2.PdfFileReader(f)
        # getNumPages can fail if the PDF, or an object therein, is
        # corrupt
        try:
            return reader.getNumPages()
        except Exception as e:
            lg.error(json1.json_msg(109,
                                    "Failure to open or parse a PDF file - possible indication of a corrupt PDF",
                                    None,
                                    file=pdf_file))
            raise e

def pdf_page_to_png(src_pdf, pagenum = 0, resolution = 72):
    """
    Return the specified PDF page as a wand.image.Image png.
    :param PyPDF2.PdfFileReader src_pdf: PDF from which to take pages.
    :param int pagenum: Page number to take.
    :param int resolution: Resolution for resulting png in DPI.
    """
    dst_pdf = PyPDF2.PdfFileWriter()
    dst_pdf.addPage(src_pdf.getPage(pagenum))

    pdf_bytes = io.BytesIO()
    dst_pdf.write(pdf_bytes)
    pdf_bytes.seek(0)

    img = Image(file = pdf_bytes, resolution = resolution)
    img.convert("png")
    return img

def pdf_split(input_pdf_file,output_files,page_ranges):
    """
    INPUT_PDF_FILE is a string representing the path to a PDF file.
    OUTPUT_FILES is a list of strings representing paths to output
    files corresponding to the specified page ranges. PAGE_RANGES is
    an array of tuples where each tuple specifies the first page and
    the last page of a given set of pages.
    """
    reader = PyPDF2.PdfFileReader(input_pdf_file)
    for output_file, page_range in zip(output_files,page_ranges):
        writer = PyPDF2.PdfFileWriter()
        pdf_split_internal(reader,writer,page_range)
        output_file = open(output_file,"wb")
        writer.write(output_file)
        output_file.close()

def pdf_split_internal (pdf_file_reader,pdf_file_writer,page_range):
    """
    The reader and writer are PyPDF2 objects. Add the pages, specified
    by PAGE_RANGE, from specified reader object to the specified
    writer object. PAGE_RANGE is a tuple where the elements are
    integers defining the first and last page (inclusive) in the page
    range. Page count begins at 1.
    """
    # Adjust page numbers as PyPDF2 counts pages beginning at zero.
    pages = list(range(page_range[0]-1,page_range[1]))
    for page_index in pages:
        pdf_file_writer.addPage(pdf_file_reader.getPage(page_index))

def pdf_to_pngs(pdf_file,output_dir):
    """
    Generate PNG files, one corresponding to each page of the PDF file
    PDF_FILE. Write files to directory specified by OUTPUT_DIR. Return
    a list of the PNG file names.
    """
    input_file_sans_suffix, input_file_suffix = os.path.splitext(pdf_file)
    maybe_dir, input_file_name_only = os.path.split(input_file_sans_suffix)
    number_of_pages = None
    outfile_root = input_file_name_only
    number_of_pages = pdf_number_of_pages(pdf_file)
    lg.info(json1.json_pdf_info(number_of_pages))
    return pdf_to_pngs__pdftoppm(pdf_file,
                                 number_of_pages,
                                 outfile_root,
                                 output_dir)

def pdf_to_pngs__gs (pdf_file, number_of_pages, outfile_root, output_dir):
    """
    Helper relying on Ghostscript. Return a list of file names.
    """
    # see common-lisp/tt-cover-sheets/conversion-of-pdf-to-png-and-zbar.txt
    pdf_to_png_res = "72"      # 72 dpi
    output_dir_and_filename = os.path.join(output_dir,outfile_root)
    # %03d is printf directive directing gs to specify page number as a zero-padded 3-digit sequence
    output_path_spec = output_dir_and_filename + '-%03d.png'
    # issue: gs doesn't give feedback regarding extent of progress
    gs_command = [
        "gs",
        "-q",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pnggray",
        '-r'+pdf_to_png_res,
        #"-dAutoRotatePages=/PageByPage",
        '-dUseCropBox',
        # use %d as a printf format specification for page number
        # as zero-filled with minimum of three spaces
        "-sOutputFile=%s" % output_path_spec,
        pdf_file
    ]
    return_code = subprocess.call(gs_command, shell=False)
    # log success/failure
    pdf_to_pngs__gs_log(return_code,number_of_pages)
    # return file names
    return pdf_to_pngs__gs_file_names (number_of_pages,outfile_root)

def pdf_to_pngs__gs_log (return_code,number_of_pages):
    if (return_code == 0):
        for page_number in range(number_of_pages):
            lg.info(json1.json_completed_pdf_to_ppm(page_number,number_of_pages))
    else:
        lg.error(json1.json_failed_to_convert_pdf(None,pdf_file))

def pdf_to_pngs__gs_file_names (number_of_pages,outfile_root):
    png_files=[]
    index_format_string = "{1:0>03d}"
    string_format_string = "{0}-" + index_format_string + ".png"
    for pagenumber in range(number_of_pages):
        png_infile = str.format(
            string_format_string,
            outfile_root,pagenumber+1);
        png_files.append(png_infile)
    return png_files

def pdf_to_pngs__pdftoppm (pdf_file, number_of_pages, outfile_root, output_dir):
    """
    Helper relying on pdftoppm. OUTFILE_ROOT is the filename only (no
    directory information). Return a list where each member has the
    form (<file name>,<page number>) with page numbering beginning at
    one.
    """
    output_dir_and_filename = os.path.join(output_dir,outfile_root)
    # Q: what is the point of calling pdftoppm repeatedly on each page, one at a time? doesn't this generate the exact same set of files as calling it just once w/o the -f and -l options?
    for page_number in range(number_of_pages):
        returncode = subprocess.call(
            ["pdftoppm", "-f", str(page_number+1),
             "-l", str(page_number+1),
             "-gray",
             "-png",
             pdf_file,
             output_dir_and_filename],
            shell=False)
        if (returncode == 0):
            lg.info(json1.json_completed_pdf_to_ppm(page_number,number_of_pages))
        else:
            lg.error(json1.json_failed_to_convert_pdf(None,pdf_file))
    # Return an array where each member has the form
    # (<file name>,<page number>)
    return_value = []
    # Due to the inability to configure the output file name format
    # for pdftoppm, plan ahead for the file names, anticipating
    # pdftoppm's default non-configurable behavior.
    index_format_string = ""
    if ( number_of_pages < 10 ):
        index_format_string = "{1:d}"
    elif ( number_of_pages < 100 ):
        index_format_string = "{1:0>02d}"
    elif ( number_of_pages < 1000 ):
        index_format_string = "{1:0>03d}"
    else:
        raise Exception('no support (at this point) for page count exceeding 1000 pages')
    string_format_string = "{0}-" + index_format_string + ".png"
    for pagenumber in range(number_of_pages):
        png_file = str.format(
            string_format_string,
            outfile_root, # output_dir_and_filename
            pagenumber+1);
        return_value.append((png_file,
                             pagenumber+1
                             ))
    return return_value

def pdfimages(pdf_file,output_dir):
    """
    Generate PNG files, one corresponding to each image in the PDF
    file PDF_FILE. Write files to directory specified by OUTPUT_DIR.

    Return tuples where each member has the form (png-file-name,
    page-number) where png-file-name is a string representing the name
    of the file and page-number represents the page number in the
    corresponding PDF file. Page numbering begins at 1.
    """
    input_file_sans_suffix, input_file_suffix = os.path.splitext(pdf_file)
    maybe_dir, input_file_name_only = os.path.split(input_file_sans_suffix)
    outfile_root = input_file_name_only
    output_dir_and_filename = os.path.join(output_dir,outfile_root)
    returncode = subprocess.call(
        ["pdfimages", "-p", "-png", pdf_file, output_dir_and_filename],
        shell=False)
    if (returncode == 0):
        # FIXME: this is a problem if other programs rely on this -- should be in docstring if it's guaranteed to log this
        #lg.info(json1.json_completed_pdf_to_ppm(page_number,number_of_pages))
        lg.info(json1.json_completed_pdf_to_ppm(-1,-1))
    else:
        lg.error(json1.json_failed_to_convert_pdf(None,pdf_file))
    # return values
    png_file_page_number_tuples=[]
    # file names have the form <image root>-<page number>-<image number>.png where the numbers are 3-digit zero-padded values
    # - it would be great if pdfimages, w/o a single invocation, could (1) extract images *and* (2) provide list of images
    dir_files = os.listdir(output_dir)
    outfile_root_re = re.compile("^"+outfile_root+"-(\d{1,3}\d{1,3}\d{1,3})-\d{1,3}\d{1,3}\d{1,3}\.png$")
    for dir_file in dir_files:
        png_file_match = outfile_root_re.match(dir_file)
        if png_file_match:
            png_file_page_number_tuples.append(
                ( png_file_match.group(),
                  int(png_file_match.group(1))
                )
            )
    return png_file_page_number_tuples
