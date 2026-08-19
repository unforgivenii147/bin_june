#!/data/data/com.termux/files/home/.local/bin/python
import pdfplumber
from joblib import Parallel, delayed


def extract_single_page_plumber(page_data):
    page_num, pdf_path, output_dir = page_data
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num - 1]
            text = page.extract_text() or ""

        page_file = output_dir / f"page_{page_num:03d}.txt"
        page_file.write_text(text, encoding="utf-8")
        return page_num, page_file
    except Exception as e:
        print(f"Error extracting page {page_num}: {e}", file=sys.stderr)
        return None


def extract_pages_from_pdf_plumber(pdf_path, n_jobs=4):
    pdf_path = Path(pdf_path)
    output_dir = pdf_path.parent / pdf_path.stem
    output_dir.mkdir(exist_ok=True)

    # Get total pages
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

    pages_data = [(page_num, pdf_path, output_dir) for page_num in range(1, total_pages + 1)]

    page_results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(extract_single_page_plumber)(page_data) for page_data in pages_data
    )

    return [result for result in page_results if result is not None]
