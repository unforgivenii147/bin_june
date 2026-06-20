#!/data/data/com.termux/files/usr/bin/python

import base64
import os
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import AttributeValueList


def encode_local_file_to_base64(file_path) -> str | None:
    try:
        with Path(file_path).open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        print(f"Internal Error: encode_local_file_to_base64 called with non-existent file: {file_path}")
        return None
    except Exception as e:
        print(f"Error encoding file {file_path}: {e}")
        return None


def find_local_resource(resource_name: AttributeValueList | str, base_html_dir: Path | str):
    search_paths = [Path("/sdcard/_static"), Path(base_html_dir), Path.cwd(), Path(base_html_dir).parent.parent]
    normalized_resource_name = resource_name
    if normalized_resource_name.startswith("/"):
        normalized_resource_name = normalized_resource_name.lstrip("/")
    for search_dir in search_paths:
        abs_search_dir = Path(str(search_dir)).resolve()
        potential_path = os.path.join(abs_search_dir, normalized_resource_name)
        if Path(potential_path).exists():
            print(f"Found resource '{resource_name}' at: {potential_path}")
            return potential_path
        path_relative_to_html_dir = os.path.join(base_html_dir, resource_name)
        if Path(path_relative_to_html_dir).exists():
            print(f"Found resource '{resource_name}' relative to HTML dir: {path_relative_to_html_dir}")
            return path_relative_to_html_dir
        if resource_name.startswith("/"):
            path_stripped_slash = os.path.join(base_html_dir, resource_name.lstrip("/"))
            if Path(path_stripped_slash).exists():
                print(f"Found resource '{resource_name}' (stripped slash) relative to HTML dir: {path_stripped_slash}")
                return path_stripped_slash
        fallback_search_dirs = [Path.cwd(), os.path.join(Path.cwd(), os.pardir), os.path.join(base_html_dir, os.pardir)]
        for fallback_dir in fallback_search_dirs:
            abs_fallback_dir = Path(fallback_dir).resolve()
            potential_path = os.path.join(abs_fallback_dir, resource_name)
            if Path(potential_path).exists():
                print(f"Found resource '{resource_name}' in fallback dir {abs_fallback_dir}: {potential_path}")
                return potential_path
            if resource_name.startswith("/"):
                potential_path_stripped = os.path.join(abs_fallback_dir, resource_name.lstrip("/"))
                if Path(potential_path_stripped).exists():
                    print(
                        f"Found resource '{resource_name}' (stripped slash) in fallback dir {abs_fallback_dir}: {potential_path_stripped}"
                    )
                    return potential_path_stripped
    print(f"Resource '{resource_name}' not found in primary or fallback locations.")
    return None


def make_html_standalone(path: Path) -> str:
    html_content = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    base_html_dir = str(path.parent)
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src")
        if src and (not src.startswith(("http://", "https://", "data:"))):
            local_img_path = find_local_resource(src, base_html_dir)
            if local_img_path:
                encoded_img = encode_local_file_to_base64(local_img_path)
                if encoded_img:
                    img_tag["src"] = f"data:{get_mime_type(local_img_path)};base64,{encoded_img}"
            else:
                print(f"Warning: Image resource '{src}' not found, removing tag.")
                img_tag.decompose()
    for link_tag in soup.find_all("link"):
        if link_tag.get("rel") == ["stylesheet"]:
            href = link_tag.get("href")
            if href and (not href.startswith(("http://", "https://", "data:"))):
                local_css_path = find_local_resource(href, base_html_dir)
                if local_css_path:
                    print(f"Processing CSS file: {local_css_path}")
                    try:
                        css_content = Path(local_css_path).read_text(encoding="utf-8")
                        font_url_matches = re.findall(
                            "url\\s*\\(\\s*[\\'\"]?([^\\'\"\\)]+)[\\'\"]?\\s*\\)", css_content
                        )
                        for font_url in font_url_matches:
                            if not font_url.startswith(("http://", "https://", "data:")):
                                local_font_path = find_local_resource(font_url, Path(local_css_path).parent)
                                if local_font_path:
                                    encoded_font = encode_local_file_to_base64(local_font_path)
                                    if encoded_font:
                                        mime_type = get_mime_type(local_font_path)
                                        css_content = re.sub(
                                            re.escape(f"url({font_url})").replace("\\(", "\\(").replace("\\)", "\\)"),
                                            f"url('data:{mime_type};base64,{encoded_font}')",
                                            css_content,
                                            flags=re.IGNORECASE,
                                        )
                                else:
                                    print(
                                        f"Warning: Font file '{font_url}' referenced in CSS not found, leaving reference."
                                    )
                        style_tag = soup.new_tag("style")
                        style_tag.string = css_content
                        link_tag.replace_with(style_tag)
                    except Exception as e:
                        print(f"Error processing CSS file {local_css_path}: {e}")
                        link_tag.decompose()
                else:
                    print(f"Warning: CSS resource '{href}' not found, removing link tag.")
                    link_tag.decompose()
    for style_tag in soup.find_all("style"):
        style_content = style_tag.string
        if style_content:
            font_url_matches = re.findall("url\\s*\\(\\s*[\\'\"]?([^\\'\"\\)]+)[\\'\"]?\\s*\\)", style_content)
            for font_url in font_url_matches:
                if not font_url.startswith(("http://", "https://", "data:")):
                    local_font_path = find_local_resource(font_url, base_html_dir)
                    if local_font_path:
                        encoded_font = encode_local_file_to_base64(local_font_path)
                        if encoded_font:
                            mime_type = get_mime_type(local_font_path)
                            style_content = re.sub(
                                re.escape(f"url({font_url})").replace("\\(", "\\(").replace("\\)", "\\)"),
                                f"url('data:{mime_type};base64,{encoded_font}')",
                                style_content,
                                flags=re.IGNORECASE,
                            )
                    else:
                        print(
                            f"Warning: Font file '{font_url}' referenced in inline style not found, leaving reference."
                        )
            style_tag.string = style_content
    for script_tag in soup.find_all("script"):
        src = script_tag.get("src")
        if src and (not src.startswith(("http://", "https://", "data:"))):
            local_script_path = find_local_resource(src, base_html_dir)
            if local_script_path:
                try:
                    script_content = Path(local_script_path).read_text(encoding="utf-8")
                    script_tag.string = script_content
                    script_tag["src"] = ""
                except Exception as e:
                    print(f"Error reading script content from {local_script_path}: {e}")
                    script_tag.decompose()
            else:
                print(f"Warning: Local script resource '{src}' not found, removing tag.")
                script_tag.decompose()
        elif not src:
            pass
        elif src.startswith(("http://", "https://")):
            print(f"Removing external script: {src}")
            script_tag.decompose()
    return soup.prettify()


def get_mime_type(file_path) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".eot": "application/vnd.ms-fontobject",
        ".js": "application/javascript",
        ".css": "text/css",
    }
    return mime_map.get(ext, "application/octet-stream")


if __name__ == "__main__":
    input_path = Path(sys.argv[1])
    output_file = input_path.stem + "_standalone" + input_path.suffix
    output_path = input_path.with_name(output_file)
    standalone_html = make_html_standalone(input_path)
    if standalone_html:
        try:
            output_path.write_text(standalone_html, encoding="utf-8")
            print(f"Standalone HTML saved to: {output_file}")
        except Exception as e:
            print(f"Error writing to output file {output_file}: {e}")
