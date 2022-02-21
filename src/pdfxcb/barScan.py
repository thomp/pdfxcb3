import imp
import sys

import logging

import pdfxcb.json1 as json1


lg=logging


try:
    imp.find_module('zbar')
except ImportError:
    msg = json1.json_msg_module_not_accessible('zbar')
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit(msg)
import zbar


# Image is provided by PIL (python 2) or pillow (python 3; debian
# supplies this as python3-pil)
try:
    imp.find_module('PIL')
except ImportError:
    msg = json1.json_msg_module_not_accessible('PIL')
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit(msg)
from PIL import Image



def barcodeScan(imagePNGPath, scan_region):
    """
    imagePNGPath should be a string defining the location of a PNG
    file. Return None if a barcode was not found. If a barcode was
    found, return a string corresponding to the barcode-encoded data.

    Search within the region defined by SCAN_REGION when SCAN_REGION
    is a list. When SCAN_REGION is a list, it specifies two points as
    [x1,y1,x2,y2]. The two points, (x1,y1) and (x2,y2), are pairs
    (x,y) of percentages (each expressed as a value between 0 and 1.0)
    relative to the dimensions of the image; they define the box
    within which the barcode scan occurs.

    If SCAN_REGION is not a list, the full image is analyzed. If
    analysis of the full image is desirable, do not set SCAN_REGION to
    [0,0,1,1] but instead set it to None or some other non-list value.
    """
    # sanity check(s)
    if not isinstance(scan_region,list):
        scan_region = None
    else:
        for value in scan_region:
            if (value < 0 or value > 1):
                msg = json1.json_msg(999,"insane scan region value",False,None)
                lg.error(msg)
                lg.info(json1.json_last_log_msg())
                sys.exit(msg)
    # obtain image data either via PIL or CV2/numpy
    #   1. using pil
    # PIL origin (0,0) is top left corner
    pil = Image.open(imagePNGPath).convert('L') # 'L' is "black and white mode": converts to 8-bit pixels B/W
    #   2. using cv2/numpy
    #pil_1 = Image.open(imagePNGPath)
    #frame = pil_1.convert("RGB")
    #pil_gray = cv2.cvtColor(numpy.array(frame), cv2.COLOR_BGR2GRAY, dstCn=0)
    #pil = Image.fromarray(pil_gray)
    pilCropped = pil
    width, height = pil.size
    if scan_region:
        # relative (percentage) values between 0 and 1
        x_crop_min = min(scan_region[0],scan_region[2])
        x_crop_max = max(scan_region[0],scan_region[2])
        y_crop_min = min(scan_region[1],scan_region[3])
        y_crop_max = max(scan_region[1],scan_region[3])
        cropTop=int(height*y_crop_min)
        cropBottom=int(height*y_crop_max)
        cropLeft=int(height*x_crop_min)
        cropRight=int(height*x_crop_max)
        # crop box is 4-tuple: left,upper,right,lower
        pilCropBox = [cropLeft,cropTop,cropRight,cropBottom]
        pilCropped = pil.crop(pilCropBox)
    #  zbar sometimes catches a barcode at a lower resolution but
    #  misses it at a higher resolution. Scan for barcode with several
    #  variants of image specified by IMAGE_FILE_SPEC.
    barcodeString = barcode_scan_at_resolutions(pilCropped,None)
    if ( not barcodeString ):
            lg.warn(json1.json_barcode_not_found_msg([imagePNGPath],""))
    return barcodeString

def barcode_scan_at_resolutions (pil,scale_values):
    """
    Try scans at multiple image resolutions since zbar sometimes is
    befuddled by high resolution images.
    """
    if scale_values == [] :
        # done - empty array indicates all scale values have been tried
        return None;
    elif ( not scale_values ):
        # Options for leveraging zbar:
        # (1) via shell invocation and (2) via python zbar library
        #barcodeString = barcodeScan_zbarimg (pil)
        barcodeString = barcodeScan_python_zbar_sub (pil)
        if ( barcodeString ):
            return barcodeString
        else:
            scale_values = [ 0.5 ]
            return barcode_scan_at_resolutions(pil,scale_values)
    else:
        scale_value = scale_values.pop()
        resize_x = int(round(scale_value * pil.size[0]))
        resize_y = int(round(scale_value * pil.size[1]))
        pil_scaled = pil.resize( (resize_x, resize_y) )
        barcodeString = barcodeScan_python_zbar_sub (pil_scaled)
        if ( barcodeString ):
            return barcodeString
        else:
            return barcode_scan_at_resolutions(pil,scale_values)

def barcodeScan_zbarimg (pil):
    """
    If possible, return the string encoded by the barcode in the image
    specified by PIL.
    """
    barcodeString = None
    tf = tempfile.NamedTemporaryFile()
    pil.save(tf,"png")
    code_type_pairs,return_val = zbarimg(tf.name)
    lg.debug("code_type_pairs: %s",code_type_pairs)
    for code_type_pair in code_type_pairs:
        barcodeString = code_type_pair[0]
    tf.close()
    return barcodeString

def barcodeScan_python_zbar_sub (pilCropped):
    pilCroppedWidth,pilCroppedHeight = pilCropped.size
    raw = pilCropped.tobytes()
    # wrap raw image data in zbar.Image
    image = zbar.Image(pilCroppedWidth, pilCroppedHeight, 'Y800', raw)
    # create and configure a reader
    scanner = zbar.ImageScanner()
    scanner.parse_config('enable')
    # scan the image for barcodes
    scanner.scan(image)
    # extract results
    barcodeString = None
    # image.symbols should hold a zbar.SymbolSet object
    for symbol in image:
        barcodeString = symbol.data
    # clean up (destroy the image object to free up references to the data and symbols)
    # - note: if another image will be scanned, it's also possible to simply recycle the image object
    del(image)
    return barcodeString

def zbarimgWithPopen (path):
    """
    PATH can correspond to any file which the zbarimg executable can handle.
    """
    # limit to CODE128?
    # -Sdisable -Scode128.enable
    p = subprocess.Popen(['zbarimg',path],shell=False,stdout=subprocess.PIPE)
    lines = p.stdout.readlines()
    retval = p.wait()
    return parse_zbarimg_lines(lines),retval

# zbarimgWithCheckOutput
def zbarimg (path):
    """
    PATH can correspond to any file which the zbarimg executable can
    handle. Return multiple values. The first value returned is a list
    of lists; each sublist contains two members, the encoded string
    and the encoding system. The second value returned is an integer
    representing the return code (exit status) associated with
    invocation of zbarimg.
    """
    # limit to CODE128?
    # -Sdisable -Scode128.enable
    output = None
    returncode = None
    try:
        output = subprocess.check_output(
            ['zbarimg',path],
            shell=False,
            stderr=subprocess.STDOUT)
        returncode = 0
    except subprocess.CalledProcessError as e:
        returncode = e.returncode
        output = e.output
    lines = output.splitlines()
    return parse_zbarimg_lines(lines),returncode

def parse_zbarimg_line (line):
    """
    LINE is a string corresponding to a single line of zbarimg
    output. Return the encoded string and the encoding system.
    """
    # example line: 'CODE-128:1000642\n'
    line = line.rstrip()
    colon_index = line.find(':')
    return line[colon_index+1:],line[:colon_index]

def parse_zbarimg_lines (lines):
    parsed_lines = []
    for line in lines:
        parsed_line,code = parse_zbarimg_line(line)
        parsed_lines.append([parsed_line,code])
    return parsed_lines

if __name__ == "__main__":
    import sys
    # log to console when executing directly
    lg.basicConfig(stream=sys.stderr,level=logging.DEBUG)
    # only intended to be run as python ./barScan.py "/path/to/foo.png"
    lg.debug("%s",sys.argv)
    if len(sys.argv) > 1:
        barcodeScan(sys.argv[1])
    else:
        sys.exit("Must supply a single file as argument")
