import json
import datetime
import time


def json_msg(code,message,outfile,
             data=None,file=None,files=None,pdffile=None,pngfiles=None):
    """
    Return a string or, if OUTFILE is a string, send to the file
    corresponding to OUTFILE. The output should be a JSON object with a
    code slot, a message slot, a time slot, a microsec slot, and
    additional slots as specified by the function's additional
    arguments/parameters.

    If message is an array, the first member of MESSAGE should be
    succinct and not disclose excessive detail. The intent is that
    this string could serve as an update for a non-technical end-user.
    """
    # if appendp is True (the default), create file if nonexistent; append if existent
    appendp=True
    if appendp:
        openMode='a+'
    else:
        openMode='w+'
    obj = json_msg_obj(code,
                       message,
                       data=data,
                       file=file,
                       files=files,
                       pdffile=pdffile,
                       pngfiles=pngfiles)
    if outfile:
        with open(outfile, openMode) as outfp:
            json.dump(obj, outfp)
    else:
        return json.dumps(obj)

def json_msg_obj(code,message,
                 data=None,file=None,files=None,pdffile=None,pngfiles=None):
    """Return an object."""
    obj = {}
    obj['code'] = code
    obj['message'] = message
    obj['time'] = int(time.time())
    obj['microsec'] = datetime.datetime.now().microsecond
    if data:
        obj['data'] = data
    if file:
        obj['file'] = file
    if files:
        obj['files'] = files
    if pdffile:
        obj['pdffile'] = pdffile
    if pngfiles:
        obj['pngfiles'] = pngfiles
    return obj

#
# messages
#
def json_barcode_not_found_msg(files,msg):
    """
    FILES is an array where each member is a string specifying the
    location of a diagnostic image file. MSG is additional data
    encapsulated as a string.
    """
    message = ['Barcode was not found',
               'see diagnostic image file(s) at {}'.format(files)
               ]
    if msg:
        message.append(msg);
    return json_msg(135, message, False,None)

def json_blank_page_on_deskew(file):
    """Return a string"""
    return json_msg(121,
                    "encountered blank page on attempt to deskew",
                    False,file=file)

def json_completed_pdf_to_ppm(page_number,number_of_pages):
    """Return a string"""
    return json_msg(11,
                    'Completed PDF to PPM conversion: page {} / {}'.format(page_number,number_of_pages),
                    False,None)

def json_converting_pdf(file):
    """Return a string"""
    return json_msg(0,
                    "Converting the PDF to PNG images... this may take some time...",
                    False,file=file)

def json_directory_not_found(dir):
    return json_msg(136,
                    'Directory not found; directory: {}'.format(dir),
                    False,None)

def json_first_log_msg(identifier,files=None):
    """Return a string. Use for the first log message."""
    obj = json_msg_obj(3,"Logging initiated")
    obj['id'] = identifier
    obj['files'] = files
    return json.dumps(obj)

def json_last_log_msg():
    """Return a string. Use for the last log message."""
    return json_msg(2,
                    "Scan and analysis complete",
                    False,None)

def json_msg_executable_not_accessible(executable_name):
    """EXECUTABLE_NAME is a string."""
    return json_msg(134,
             'The executable ' + executable_name + ' is not accessible. Is it installed?',
             False,None)

def json_exit_on_external_request_msg():
    return json_msg(4,
                    "Received external request to terminate process",
                    False,None)

def json_failed_to_convert_pdf(exception,PDFFileSpec):
    return json_msg(110,
                    ['Failed to convert PDF to PNG(s)', str(exception)],
                    False,
                    files=PDFFileSpec)

# ideally, pngFile specifies the absolute path to an image with as
# much diagnostic or explanatory information as possible to assist the
# end-user in understanding why the deskew failed
def json_failed_to_deskew(pngFile,pageNumber,comments):
    message = 'Failed to deskew at page {}'.format(pageNumber)
    message = message + " " + comments
    return json_msg(120,
                    message,
                    False,
                    files=[pngFile])

def json_failed_to_parse_file(exception,someFile):
    return json_msg(131,
                    ['Failed to parse file', str(exception)],
                    False,file=someFile)

def json_file_not_found(file):
    return json_msg(132,
                    'File not found; file: {}'.format(file),
                    False,None)

# FILES is an array where each member is a string specifying the location of a diagnostic image file. This is only generated if debug_p flag is set in code of interest.

# RECT should be an array with two points [(x1,y1),(x2,y2)] defining a rectangle centered on and surrounding the area of interest. DIM should be an array with two values, the width (x) and the length (y) of the image. Units for components of DIM should be the same units as those used for components of RECT. PAGE_N is the page number relative to the document specified by PDF_FILE.

# this log message should allow any client, given the PDF file under consideration, to generate a diagnostic image
def json_msg_bubble_not_found(files,msg,rect,dim,page_n):
    """MSG is additional data encapsulated as a string"""
    data = { "files": files,
             "area":  rect,
             "dimensions": dim,
             "page_n": page_n
    }
    message = ['anticipated a bubble at position but bubble was not found', 'see diagnostic image files']
    if msg:
        message.append(msg)
    return json_msg(133, message, False, data=data)

def json_msg_bubbles_not_found(file,msg):
    """
    FILE is a single string specifying the location of a diagnostic
    image file. MSG is additional data encapsulated as a string. This
    is intended to be used to provide summary information to the end
    user. Individual bubble issues should be logged with
    json_msg_bubble_not_found.
    """
    message = ['Unable to find one or more bubbles', 'see diagnostic image file']
    if msg:
        message.append(msg)
    return json_msg(134, message, False, file=file)

def json_msg_module_not_accessible(module_name):
    """MODULE_NAME is a string."""
    return json_msg(140,
                    'The python module ' + module_name + ' is not accessible. Is it installed?',
                    False,None)

# File size (kB), resolution, file name, etc. might also be of interest at some point.
def json_pdf_info(number_of_pages):
    """Provide description of the PDF under consideration."""
    pdf_data = { 'number_of_pages': number_of_pages }
    return json_msg(70,
                    "PDF information",
                    False, data=pdf_data)

def json_pdf_to_pngs_success(pdffile,png_specs):
    """
    Return a string. PNG_SPECS is an array of (<file_name>,<page_number>)
    tuples.
    """
    return json_msg(10,
                    "Successfully converted PDF to PNG(s)",
                    False,
                    pdffile=pdffile)

def json_progress(progress_message):
    """
    Use to provide an informational message indicating extent of
    progress.
    """
    return json_msg(50, progress_message, False)

def json_scanset(scanSet):
    return json_msg(30,
                    'scanset',
                    False, data=scanSet);

def json_scansets(scanSets):
    return json.dumps(scanSets)

def json_successful_deskew(file):
    """Return a string"""
    return json_msg(20,
                    "Successful deskew",
                    False, file=file)
