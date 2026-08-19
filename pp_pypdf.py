#!/data/data/com.termux/files/home/.local/bin/python
from pypdf import PdfReader


def extract_pages_from_pdf_pypdf(pdf_path, n_jobs=4):
    pdf_path = Path(pdf_path)
    output_dir = pdf_path.parent / pdf_path.stem
    output_dir.mkdir(exist_ok=True)

    reader = PdfReader(pdf_path)

    def extract_page(page_num):
        try:
            page = reader.pages[page_num - 1]
            text = page.extract_text()
            page_file = output_dir / f"page_{page_num:03d}.txt"
            page_file.write_text(text, encoding="utf-8")
            return page_num, page_file
        except Exception as e:
            print(f"Error extracting page {page_num}: {e}", file=sys.stderr)
            return None

    results = Parallel(n_jobs=n_jobs, backend="threading")(
        delayed(extract_page)(i) for i in range(1, len(reader.pages) + 1)
    )

    return [r for r in results if r is not None]
