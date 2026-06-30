#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path
from weasyprint import CSS, HTML


def html2pdf(
    pdf_file_path, html_file_path=None, css_file_path: str = "/sdcard/_static/css/markdown.css", base_url=None
) -> None:
    raw_html = ""
    extras = ["cuddled-lists", "tables"]
    if html_file_path:
        raw_html = html_file_path.read_text(encoding="utf8")
    html = HTML(string=raw_html, base_url=base_url)
    css = []
    if css_file_path:
        css.append(CSS(filename=css_file_path))
    html.write_pdf(pdf_file_path, stylesheets=css)


if __name__ == "__main__":
    html_file = Path(sys.argv[1])
    pdf_file = html_file.with_suffix(".pdf")
    html2pdf(pdf_file_path=pdf_file, html_file_path=html_file)
