#!/data/data/com.termux/files/usr/bin/python

import re

from weasyprint import HTML

INPUT_FILE = "dictionary.txt"
OUTPUT_FILE = "dictionary.pdf"
CUSTOM_FONT = "custom.ttf"


def convert_entry_to_html(raw_line: str) -> str | None:
    try:
        word, html_body = raw_line.strip().split("\t", 1)
    except ValueError:
        return None
    html_body = html_body.replace("<br />", "<br>")
    html_body = re.sub("</?[CFINEË]+[^>]*>", "", html_body)
    html_body = re.sub("<x [^>]*>", "<span>", html_body)
    html_body = html_body.replace("</x>", "</span>")
    html_body = re.sub('<Ë M="[^"]+" ?/?>', "", html_body)
    return f'\n    <html>\n    <body>\n        <div class="entry">\n            <h1 class="word">{word}</h1>\n            <div class="definition">{html_body}</div>\n        </div>\n    </body>\n    </html>\n    '


def main() -> None:
    with open(INPUT_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    pages = []
    for line in lines:
        html = convert_entry_to_html(line)
        if html:
            pages.append(html)
    full_html = f"""\n    <html>\n        <head>\n            <style>\n                @font-face {{\n                    font-family: "CustomFont";\n                    src: url('{CUSTOM_FONT}');\n                }}\n                body {{\n                    font-family: "CustomFont", sans-serif;\n                    font-size: 16px;\n                }}\n                .entry {{\n                    page-break-after: always;\n                    padding: 30px;\n                }}\n                .word {{\n                    margin-top: 0;\n                    color:\n                }}\n                .definition {{\n                    margin-top: 10px;\n                    line-height: 1.5;\n                }}\n            </style>\n        </head>\n        <body>\n    """
    for p in pages:
        full_html += p
    full_html += "</body></html>"
    HTML(string=full_html).write_pdf(OUTPUT_FILE)
    print("PDF created:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
