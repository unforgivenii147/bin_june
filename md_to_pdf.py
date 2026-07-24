#!/data/data/com.termux/files/home/.local/bin/python
import sys
from pathlib import Path
import markdown
import weasyprint

# The optimized CSS content from the previous response
CSS_TEMPLATE = """
/* ==========================================================================
   1. PAGE SETUP & PAGED MEDIA
   ========================================================================== */
@page {
    size: A4;
    margin: 20mm;
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 9pt;
        color: #888888;
    }
}

h1, h2, h3, h4, h5, h6 { page-break-after: avoid; break-after: avoid; }
blockquote, pre, table, figure { page-break-inside: avoid; break-inside: avoid; }
ul, ol { page-break-inside: auto; }
li { page-break-inside: avoid; break-inside: avoid; }

/* ==========================================================================
   2. TYPOGRAPHY & BASE STYLES
   ========================================================================== */
html, body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #333333;
}

p {
    margin-top: 0;
    margin-bottom: 1.2em;
    text-align: justify;
}

h1 {
    font-size: 24pt;
    margin-top: 0;
    margin-bottom: 15pt;
    color: #111111;
    border-bottom: 2px solid #eeeeee;
    padding-bottom: 5pt;
}

h2 {
    font-size: 18pt;
    margin-top: 24pt;
    margin-bottom: 12pt;
    color: #222222;
    border-bottom: 1px solid #eeeeee;
    padding-bottom: 3pt;
}

h3 {
    font-size: 14pt;
    margin-top: 18pt;
    margin-bottom: 8pt;
    color: #444444;
}

/* ==========================================================================
   3. INLINE ELEMENTS & DECORATIONS
   ========================================================================== */
a { color: #0066cc; text-decoration: none; }
a[href^="http"]:after {
    content: " (" attr(href) ")";
    font-size: 9pt;
    color: #666666;
}

strong { color: #111111; }

code {
    font-family: "Courier New", Courier, monospace;
    font-size: 10pt;
    background-color: #f5f5f5;
    padding: 2px 4px;
    border-radius: 3px;
    color: #d14;
}

blockquote {
    margin: 1.5em 0;
    padding: 0.5em 15px;
    border-left: 4px solid #dddddd;
    color: #666666;
    background-color: #fafafa;
    font-style: italic;
}

/* ==========================================================================
   4. CODE BLOCKS (Markdown ``` )
   ========================================================================== */
pre {
    background-color: #f8f8f8;
    border: 1px solid #e1e1e8;
    border-radius: 4px;
    padding: 12px;
    margin: 1.5em 0;
    overflow: hidden;
}

pre code {
    background-color: transparent;
    padding: 0;
    border-radius: 0;
    color: #333333;
    font-size: 9.5pt;
    white-space: pre-wrap;
}

/* ==========================================================================
   5. TABLES & LISTS
   ========================================================================== */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 10.5pt;
}

th, td {
    border: 1px solid #dddddd;
    padding: 8px 12px;
    text-align: left;
}

th {
    background-color: #f5f5f5;
    font-weight: bold;
    color: #222222;
}

tr:nth-child(even) { background-color: #fafafa; }
ul, ol { margin-top: 0; margin-bottom: 1.5em; padding-left: 24px; }
li { margin-bottom: 0.4em; }

/* ==========================================================================
   6. IMAGES / FIGURES
   ========================================================================== */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 20px auto;
    border-radius: 4px;
}
"""


def convert_md_to_pdf(input_path_str: str):
    # 1. Validate the input file path
    input_file = Path(input_path_str)
    if not input_file.exists():
        print(f"❌ Error: The file '{input_path_str}' does not exist.")
        sys.exit(1)

    if input_file.suffix.lower() not in (".md", ".markdown"):
        print(f"⚠️  Warning: '{input_path_str}' does not have a standard Markdown extension.")

    # 2. Determine output path beside the input file
    output_pdf = input_file.with_suffix(".pdf")

    print(f"📖 Reading: {input_file.name}")
    try:
        md_content = input_file.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    print("🛠️  Converting Markdown to HTML...")
    # 'extra' enables tables, footnotes, and task lists
    # 'codehilite' prepares code blocks for structural cleanups
    html_body = markdown.markdown(md_content, extensions=["extra", "codehilite"])

    # Wrap in a standard HTML document boilerplate
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{input_file.stem}</title>
</head>
<body>
    {html_body}
</body>
</html>"""

    print("🚀 Compiling PDF with WeasyPrint...")
    try:
        # Pass the HTML string and attach our CSS rules directly
        html_doc = weasyprint.HTML(string=full_html, base_url=str(input_file.parent))
        css_doc = weasyprint.CSS(string=CSS_TEMPLATE)

        html_doc.write_pdf(target=output_pdf, stylesheets=[css_doc])
        print(f"✅ Success! PDF saved beside markdown file at:\n   👉 {output_pdf.resolve()}")
    except Exception as e:
        print(f"❌ WeasyPrint Compilation Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage Error: Please provide an input Markdown file path.")
        print("   Example: python md_to_pdf.py instructions.md")
        sys.exit(1)

    convert_md_to_pdf(sys.argv[1])
