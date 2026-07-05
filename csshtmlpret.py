#!/data/data/com.termux/files/usr/bin/python
import itertools
import os
import re
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from subprocess import getoutput
from time import sleep

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    print("BeautifulSoup4 Not Found, use: pip install BeautifulSoup4")
start_time = datetime.now()
CSS_PROPS_TEXT = """
alignment-adjust alignment-baseline animation animation-delay
animation-direction animation-duration animation-iteration-count
animation-name animation-play-state animation-timing-function appearance
azimuth
backface-visibility background background-blend-mode background-attachment
background-clip background-color background-image background-origin
background-position background-position-block background-position-inline
background-position-x background-position-y background-repeat background-size
baseline-shift bikeshedding bookmark-label bookmark-level bookmark-state
bookmark-target border border-bottom border-bottom-color
border-bottom-left-radius border-bottom-parts border-bottom-right-radius
border-bottom-style border-bottom-width border-clip border-clip-top
border-clip-right border-clip-bottom border-clip-left border-collapse
border-color border-corner-shape border-image border-image-outset
border-image-repeat border-image-slice border-image-source border-image-width
border-left border-left-color border-left-style border-left-parts
border-left-width border-limit border-parts border-radius border-right
border-right-color border-right-style border-right-width border-right-parts
border-spacing border-style border-top border-top-color border-top-left-radius
border-top-parts border-top-right-radius border-top-style border-top-width
border-width bottom box-decoration-break box-shadow box-sizing
caption-side clear clip color column-count column-fill column-gap column-rule
column-rule-color column-rule-style column-rule-width column-span column-width
columns content counter-increment counter-reset corners corner-shape
cue cue-after cue-before cursor
direction display drop-initial-after-adjust drop-initial-after-align
drop-initial-before-adjust drop-initial-before-align drop-initial-size
drop-initial-value
elevation empty-cells
flex flex-basis flex-direction flex-flow flex-grow flex-shrink flex-wrap fit
fit-position float font font-family font-size font-size-adjust font-stretch
font-style font-variant font-weight
grid-columns grid-rows
justify-content
hanging-punctuation height hyphenate-character hyphenate-resource hyphens
icon image-orientation image-resolution inline-box-align
left letter-spacing line-height line-stacking line-stacking-ruby
line-stacking-shift line-stacking-strategy linear-gradient list-style
list-style-image list-style-position list-style-type
margin margin-bottom margin-left margin-right margin-top marquee-direction
marquee-loop marquee-speed marquee-style max-height max-width min-height
min-width
nav-index
opacity orphans outline outline-color outline-offset outline-style
outline-width overflow overflow-style overflow-x overflow-y
padding padding-bottom padding-left padding-right padding-top page
page-break-after page-break-before page-break-inside pause pause-after
pause-before perspective perspective-origin pitch pitch-range play-during
position presentation-level
quotes
resize rest rest-after rest-before richness right rotation rotation-point
ruby-align ruby-overhang ruby-position ruby-span
size speak speak-header speak-numeral speak-punctuation speech-rate src
stress string-set
table-layout target target-name target-new target-position text-align
text-align-last text-decoration text-emphasis text-indent text-justify
text-outline text-shadow text-transform text-wrap top transform
transform-origin transition transition-delay transition-duration
transition-property transition-timing-function
unicode-bidi unicode-range
vertical-align visibility voice-balance voice-duration voice-family
voice-pitch voice-range voice-rate voice-stress voice-volume volume
white-space widows width word-break word-spacing word-wrap
z-index
"""


def _compile_props(props_text: str, grouped: bool = False) -> tuple:
    props, prefixes = [], ["-webkit-", "-khtml-", "-epub-", "-moz-", "-ms-", "-o-", ""]
    for propline in props_text.strip().lower().splitlines():
        props += [(pre + pro) for pro in propline.split(" ") for pre in prefixes]
    props = filter(lambda line: not line.startswith("#"), props)
    if not grouped:
        props = list(filter(None, props))
        return props, [0] * len(props)
    final_props, groups, g_id = [], [], 0
    for prop in props:
        if prop.strip():
            final_props.append(prop)
            groups.append(g_id)
        else:
            g_id += 1
    return final_props, groups


def _prioritify(line_of_css: str, css_props_text_as_list: tuple) -> tuple:
    sorted_css_properties, groups_by_alphabetic_order = css_props_text_as_list
    priority_integer, group_integer = 9999, 0
    for css_property in sorted_css_properties:
        if css_property.lower() == line_of_css.split(":", maxsplit=1)[0].lower().strip():
            priority_integer = sorted_css_properties.index(css_property)
            group_integer = groups_by_alphabetic_order[priority_integer]
            break
    return priority_integer, group_integer


def _props_grouper(props, pgs):
    if not props:
        return props
    props_pg = zip((_prioritify(prop, pgs) for prop in props), props, strict=False)
    props_pg = sorted(props_pg, key=lambda item: item[0][1])
    props_by_groups = (list(item[1]) for item in itertools.groupby(props_pg, key=lambda item: item[0][1]))
    props_by_groups = (sorted(item, key=lambda item: item[0][0]) for item in props_by_groups)
    props = []
    for group in props_by_groups:
        group = (item[1] for item in group)
        props += group
        props += ["\n"]
    props.pop()
    return props


def sort_properties(css_unsorted_string: str) -> str:
    css_pgs = _compile_props(CSS_PROPS_TEXT, grouped=bool(args.group))
    pattern = re.compile(r"(.*?{\r?\n?)(.*?)(}.*?)|(.*)", re.DOTALL + re.MULTILINE)
    matched_patterns = pattern.findall(css_unsorted_string)
    sorted_patterns, sorted_buffer = [], css_unsorted_string
    RE_prop = re.compile("((?:.*?)(?:;)(?:.*?\\n)|(?:.*))", re.DOTALL + re.MULTILINE)
    if len(matched_patterns) != 0:
        for matched_groups in matched_patterns:
            sorted_patterns += matched_groups[0].splitlines(True)
            props = (line.lstrip("\n") for line in RE_prop.findall(matched_groups[1]))
            props = list(filter(lambda line: line.strip("\n "), props))
            props = _props_grouper(props, css_pgs)
            sorted_patterns += props
            sorted_patterns += matched_groups[2].splitlines(True)
            sorted_patterns += matched_groups[3].splitlines(True)
        sorted_buffer = "".join(sorted_patterns)
    return sorted_buffer


def remove_empty_rules(css: str) -> str:
    return re.sub("[^\\}\\{]+\\{\\}", "", css)


def condense_zero_units(css: str) -> str:
    return re.sub(
        "([\\s:])(0)(px|em|%|in|q|ch|cm|mm|pc|pt|ex|rem|s|ms|deg|grad|rad|turn|vw|vh|vmin|vmax|fr)", "\\1\\2", css
    )


def condense_semicolons(css: str) -> str:
    return re.sub(";;+", ";", css)


def wrap_css_lines(css: str, line_length: int = 80) -> str:
    print(f"Wrapping lines to ~{line_length} max line lenght.")
    lines, line_start = [], 0
    for i, char in enumerate(css):
        if char == "}" and i - line_start >= line_length:
            lines.append(css[line_start : i + 1])
            line_start = i + 1
    if line_start < len(css):
        lines.append(css[line_start:])
    return "\n".join(lines)


def add_encoding(css: str) -> str:
    return "@charset utf-8;\n\n\n" + css if "@charset" not in css else css


def normalize_whitespace(css: str) -> str:
    css_no_trailing_whitespace = ""
    for line_of_css in css.splitlines():
        css_no_trailing_whitespace += line_of_css.rstrip() + "\n"
    css = css_no_trailing_whitespace
    css = re.sub("\\n{3}", "\n\n\n", css)
    css = re.sub("\\n{5}", "\n\n\n\n\n", css)
    css = re.sub("\\n{6,}", f"\n\n\n/*{'-' * 72}*/\n\n\n", css)
    css = css.replace(" ;\n", ";\n").replace("{\n", " {\n")
    css = re.sub("\\s{2,}{\n", " {\n", css)
    return css.replace("\t", "    ").rstrip() + "\n"


def justify_right(css: str) -> str:
    max_indent, right_justified_css = 1, ""
    for css_line in css.splitlines():
        c_1 = len(css_line.split(":")) == 2 and css_line.strip().endswith(";")
        c_2 = "{" not in css_line and "}" not in css_line and len(css_line)
        c_4 = not css_line.lstrip().lower().startswith("@import ")
        if c_1 and c_2 and c_4:
            lenght = len(css_line.split(":")[0].rstrip()) + 1
            max_indent = max(max_indent, lenght)
    for line_of_css in css.splitlines():
        c_1 = "{" not in line_of_css and "}" not in line_of_css
        c_2 = max_indent > 1 and len(line_of_css.split(":")) == 2
        c_3 = line_of_css.strip().endswith(";") and len(line_of_css)
        c_4 = "@import " not in line_of_css
        if c_1 and c_2 and c_3 and c_4:
            propert_len = len(line_of_css.split(":")[0].rstrip()) + 1
            xtra_spaces = " " * (max_indent + 1 - propert_len)
            xtra_spaces = ":" + xtra_spaces
            justified_line_of_css = ""
            justified_line_of_css = line_of_css.split(":")[0].rstrip()
            justified_line_of_css += xtra_spaces
            justified_line_of_css += line_of_css.split(":")[1].lstrip()
            right_justified_css += justified_line_of_css + "\n"
        else:
            right_justified_css += line_of_css + "\n"
    return right_justified_css if max_indent > 1 else css


def split_long_selectors(css: str) -> str:
    result = ""
    for line in css.splitlines():
        cond_1 = len(line) > 80 and "," in line and line.strip().endswith("{")
        cond_2 = line.startswith(("*", ".", "#"))
        if cond_1 and cond_2:
            result += line.replace(", ", ",").replace(",", ",\n").replace("{", "{\n")
        else:
            result += line + "\n"
    return result


def simple_replace(css: str) -> str:
    return css.replace("}\n#", "}\n\n#").replace("}\n.", "}\n\n.").replace("}\n*", "}\n\n*")


def css_prettify(css: str, justify: bool = False, extraline: bool = False) -> str:
    css = sort_properties(css)
    css = condense_zero_units(css)
    css = wrap_css_lines(css, 80)
    css = split_long_selectors(css)
    css = condense_semicolons(css)
    css = normalize_whitespace(css)
    css = justify_right(css) if justify else css
    css = add_encoding(css)
    css = simple_replace(css)
    if extraline:
        css = "\n\n".join(css.replace("\t", "    ").splitlines()) + "\n"
    return css


if BeautifulSoup:
    orig_prettify = BeautifulSoup.prettify
    regez = re.compile("^(\\s*)", re.MULTILINE)

    def prettify(self, encoding=None, formatter: str = "minimal", indent_width: int = 4) -> str:
        print("Monkey Patching BeautifulSoup on-the-fly to process HTML...")
        return regez.sub("\\1" * indent_width, orig_prettify(self, encoding, formatter))

    BeautifulSoup.prettify = prettify

    def html_prettify(html: str, extraline: bool = False) -> str:
        html = BeautifulSoup(html).prettify()
        if extraline:
            html = "\n\n".join(html.replace("\t", "    ").splitlines()) + "\n"
        return html

else:

    def html_prettify(html: str, extraline: bool = False) -> str:
        html = minidom.parseString(html).toprettyxml(indent="    ")[22:]
        if extraline:
            html = "\n\n".join(html.replace("\t", "    ").splitlines()) + "\n"
        return html


def walk2list(
    folder: str,
    target: tuple,
    omit: tuple = (),
    showhidden: bool = False,
    topdown: bool = True,
    onerror: object = None,
    followlinks: bool = False,
) -> list:
    return [
        p.resolve()
        for p in Path(folder).rglob("*")
        if p.is_file()
        and not p.name.startswith(() if showhidden else ".")
        and not p.name.endswith(omit)
        and p.name.endswith(target)
    ]


def process_multiple_files(file_path) -> None:
    file_path = Path(file_path)
    print(f"Process {os.getpid()} is processing {file_path}.")
    if args.watch:
        previous = int(file_path.stat().st_mtime)
        print(f"Process {os.getpid()} is Watching {file_path}.")
        while True:
            actual = int(file_path.stat().st_mtime)
            if previous == actual:
                sleep(60)
            else:
                previous = actual
                print(f"Modification detected on {file_path}.")
                if file_path.suffix.lower() in (".css", ".scss"):
                    process_single_css_file(str(file_path))
                else:
                    process_single_html_file(str(file_path))
    elif file_path.suffix.lower() in (".css", ".scss"):
        process_single_css_file(str(file_path))
    else:
        process_single_html_file(str(file_path))


def prefixer_extensioner(file_path: str) -> str:
    path_obj = Path(file_path)
    extension = path_obj.suffix.lower()
    filename = path_obj.stem
    filename = args.prefix + filename if args.prefix else filename
    return str(path_obj.parent / (filename + extension))


def process_single_css_file(css_file_path: str) -> str:
    global args
    original_css = Path(css_file_path).read_text(encoding="utf-8-sig")
    pretty_css = css_prettify(original_css, args.justify, args.extraline)
    if args.timestamp:
        taim = f"/* {datetime.now().replace(microsecond=0).isoformat(' ')} */ "
        pretty_css = taim + pretty_css
    min_css_file_path = prefixer_extensioner(css_file_path)
    Path(min_css_file_path).write_text(pretty_css, encoding="utf-8")
    return pretty_css


def process_single_html_file(html_file_path: str) -> str:
    with Path(html_file_path).open(encoding="utf-8-sig") as html_file:
        pretty_html = html_prettify(html_file.read(), args.extraline)
    html_file_path = prefixer_extensioner(html_file_path)
    Path(html_file_path).write_text(pretty_html, encoding="utf-8")
    return pretty_html


def make_arguments_parser() -> Namespace:
    parser = ArgumentParser(
        description=__doc__,
        epilog="""CSS-HTML-Prettify:
    Takes file or folder full path string and process all CSS/SCSS/HTML found.
    If argument is not file/folder will fail. Check Updates works on Python3.
    StdIn to StdOut is deprecated since may fail with unicode characters.
    CSS Properties are AlphaSorted,to help spot cloned ones,Selectors not.
    Watch works for whole folders, with minimum of ~60 Secs between runs.""",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("fullpath", metavar="fullpath", type=str, help="Full path to local file or folder.")
    parser.add_argument("--prefix", type=str, help="Prefix string to prepend on output filenames.")
    parser.add_argument("--timestamp", action="store_true", help="Add a Time Stamp on all CSS/SCSS output files.")
    parser.add_argument("--quiet", action="store_true", help="Quiet, Silent, force disable all Logging.")
    parser.add_argument("--after", type=str, help="Command to execute after run (Experimental).")
    parser.add_argument("--before", type=str, help="Command to execute before run (Experimental).")
    parser.add_argument("--watch", action="store_true", help="Re-Compress if file changes (Experimental).")
    parser.add_argument("--group", action="store_true", help="Group Alphabetically CSS Poperties by name.")
    parser.add_argument("--justify", action="store_true", help="Right Justify CSS Properties (Experimental).")
    parser.add_argument("--extraline", action="store_true", help="Add 1 New Line for each New Line (Experimental)")
    global args
    args = parser.parse_args()
    return args


def main() -> None:
    make_arguments_parser()
    global log
    if args.before and getoutput:
        print(getoutput(str(args.before)))
    if Path(args.fullpath).is_file() and args.fullpath.endswith((".css", ".scss")):
        print("Target is a CSS / SCSS File.")
        list_of_files = str(args.fullpath)
        process_single_css_file(args.fullpath)
    elif Path(args.fullpath).is_file() and args.fullpath.endswith((".htm", ".html")):
        print("Target is a HTML File.")
        list_of_files = str(args.fullpath)
        process_single_html_file(args.fullpath)
    elif Path(args.fullpath).is_dir():
        print("Target is a Folder with CSS / SCSS, HTML, JS.")
        print("Processing a whole Folder may take some time...")
        list_of_files = walk2list(args.fullpath, (".css", ".scss", ".html", ".htm"), ".min.css")
        pool = get_context("spawn").Pool(4)
        pool.map(process_multiple_files, list_of_files)
        pool.close()
        pool.join()
    else:
        print("File or folder not found,or cant be read,or I/O Error.")
        sys.exit(1)
    if args.after and getoutput:
        print(getoutput(str(args.after)))
    print(f"\n {'-' * 80} \n Files Processed: {list_of_files}.")
    print(f"""Number of Files Processed:
          {len(list_of_files) if isinstance(list_of_files, tuple) else 1}""")


if __name__ in "__main__":
    main()
