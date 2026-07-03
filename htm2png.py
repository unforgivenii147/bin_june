#!/data/data/com.termux/files/usr/bin/env python
from weasyprint import HTML
import cairosvg
import io


def html_to_png_cairo(html_content, output_path, width=None):
    """
    Alternative method using cairosvg instead of pdf2image.
    """
    # Generate PDF
    if html_content.startswith("<") or html_content.startswith("<!DOCTYPE"):
        html = HTML(string=html_content)
    else:
        html = HTML(filename=html_content)

    pdf_bytes = html.write_pdf()

    # Convert PDF to PNG using cairosvg
    cairosvg.svg2png(
        bytestring=pdf_bytes,
        write_to=output_path,
        output_width=width,
        scale=2.0,  # Higher quality
    )
    print(f"PNG saved to: {output_path}")
