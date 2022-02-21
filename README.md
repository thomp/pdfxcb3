# pdfxcb

*Split a PDF*

---

*pdfxcb* splits a PDF using pages with barcodes as delimiters or after every Nth page.


## Splitting a PDF using barcodes

Any page in the input PDF containing a barcode is potentially a "barcode sheet". Each barcode sheet, and those pages succeeding that page and preceding the next barcode sheet, comprise a single set of pages output as a discrete PDF file.

Each output file is named, by default, as `<encoded string>-<index>.pdf` where `<encoded string>` is the content encoded by the barcode on the barcode sheet and `<index>` is the page number of the barcode sheet relative to the input PDF. The page number is formatted as a three-digit page number (e.g., 001 or 023) unless the page number exceeds 999. Page numbering begins at one.

### Example

`pdfxcb -r 0.2 0 1 0.3 -l 0 -d ./outputdir -f ./pdfxcb.log /path/to/scans.pdf`

Invoking with `-r` causes the program to attempt to split prior to each page with a barcode in the specified page region. The arguments following the `-r` flag specify two points as x1 y1 x2 y2. The values are percentages (0 to 1.0) where (0,0) represents the top left corner of the page. These points define the scan region as a rectangle.

The above example scans roughly the upper right third of each page in the input file, `/path/to/scans.pdf`. The output files are written to `./outputdir`. A log is generated at `./pdfxcb.log`.
 
## Split every N pages

### Example
Reads as input `/input/file.pdf` and splits after every 14 pages.

`pdfxcb -e 14 -d /path/output/dir /input/file.pdf`

## Invoking from the shell
Use `pdfxcb --help`.

## Invoking from within Python

	>>> pdfxcb.lg.getLogger().setLevel(pdfxcb.lg.DEBUG)

	>>> pdfxcb.pdfxcb("/home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/test-doc-01/test-doc-01.pdf","/home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/test-doc-01/",None,False)


## Logging

A successful "run" should generate at least 3 log messages, each as a separate line in the log file: an initial log message (code 3), the results of analysis and burst/splitting (code 40), and a final log message (code 2). 

### Example of log file content

    {"microsec": 229757, "message": "Initial log message", "code": 3, "id": "96f08ca4-1746-11e8-936f-9840bb275139", "time": 1519245258}
    {"files": ["/tmp/123ABCabc-001.pdf", "/tmp/1234567890128-003.pdf"], "code": 40, "microsec": 402458, "time": 1520018355, "message": ["Analysis and burst completed"], "data": {"indices": [1, 3, 6], "barcodes": ["123ABCabc", "1234567890128"]}}
    {"microsec": 791009, "message": "Scan and analysis complete", "code": 2, "time": 1519245261}
