#!/data/data/com.termux/files/home/.local/bin/python
"""
Extract text from PDF files, saving each page as a separate text file.
Usage:
    python extract_pdf_pages.py [file_or_dir ...]
    If no arguments given, processes all PDFs in current directory recursively.
"""
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import StringIO
from pathlib import Path
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
def collect_pdf_files(inputs):
    pdf_files = []
    if not inputs:
        inputs = [Path(".")]
    for item in inputs:
        path = Path(item)
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_files.append(path)
        elif path.is_dir():
            pdf_files.extend(path.rglob("*.pdf"))
        else:
            print(f"Warning: {path} is not a valid PDF file or directory", file=sys.stderr)
    return pdf_files
def extract_pages_from_pdf(pdf_path):
    pdf_path = Path(pdf_path)
    output_dir = pdf_path.parent / pdf_path.stem
    output_dir.mkdir(exist_ok=True)
    results = []
    try:
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            document = PDFDocument(parser)
            if not document.is_extractable:
                print(f"Warning: {pdf_path} is not extractable", file=sys.stderr)
                return results
            rsrcmgr = PDFResourceManager()
            laparams = LAParams()
            for page_num, page in enumerate(PDFPage.create_pages(document), start=1):
                output_string = StringIO()
                device = TextConverter(rsrcmgr, output_string, laparams=laparams)
                interpreter = PDFPageInterpreter(rsrcmgr, device)
                interpreter.process_page(page)
                text = output_string.getvalue()
                device.close()
                output_string.close()
                page_file = output_dir / f"page_{page_num:03d}.txt"
                page_file.write_text(text, encoding="utf-8")
                results.append((page_num, page_file))
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}", file=sys.stderr)
    return results
def main():
    inputs = sys.argv[1:] if len(sys.argv) > 1 else []
    pdf_files = collect_pdf_files(inputs)
    if not pdf_files:
        print("No PDF files found.", file=sys.stderr)
        return
    print(f"Found {len(pdf_files)} PDF file(s) to process.")
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(extract_pages_from_pdf, pdf): pdf for pdf in pdf_files}
        for future in as_completed(futures):
            pdf = futures[future]
            try:
                results = future.result()
                print(f"Processed {pdf.name}: {len(results)} pages extracted")
            except Exception as e:
                print(f"Failed to process {pdf}: {e}", file=sys.stderr)
if __name__ == "__main__":
    main()
