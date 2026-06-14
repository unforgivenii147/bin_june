#!/data/data/com.termux/files/usr/bin/python

import sys

from markdown2 import markdown, markdown_path
from weasyprint import CSS, HTML


class ValidationError(Exception):
    pass


def md2pdf(
    pdf_file_path,
    md_content=None,
    md_file_path=None,
    css_file_path: str = "/sdcard/_static/css/markdown.css",
    base_url=None,
) -> None:
    raw_html = ""
    extras = ["cuddled-lists", "tables"]
    if md_file_path:
        raw_html = markdown_path(md_file_path, extras=extras)
    elif md_content:
        raw_html = markdown(md_content, extras=extras)
    if not len(raw_html):
        msg = "Input markdown seems empty"
        raise ValidationError(msg)
    html = HTML(string=raw_html, base_url=base_url)
    css = []
    if css_file_path:
        css.append(CSS(filename=css_file_path))
    html.write_pdf(pdf_file_path, stylesheets=css)


if __name__ == "__main__":
    md_file = sys.argv[1]
    pdf_file = md_file.replace(".md", ".pdf")
    md2pdf(pdf_file_path=pdf_file, md_file_path=md_file)
