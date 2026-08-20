#!/data/data/com.termux/files/home/.local/bin/python

import base64
import mimetypes
import os
import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

mimetypes.add_type("application/font-woff", ".woff")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("application/vnd.ms-fontobject", ".eot")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/json", ".json")
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; StandaloneHTML/1.0)"})


def guess_mime(url, content_type=None):
    if content_type:
        ct = content_type.split(";")[0].strip()
        if ct:
            return ct
    path = urlparse(url).path
    mime, _ = mimetypes.guess_type(path)
    return mime or "application/octet-stream"


def fetch(url, base_dir):
    if not url or url.startswith("data:"):
        return None, None
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith(("http://", "https://")):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            mime = guess_mime(url, resp.headers.get("Content-Type"))
            print(f"  ↓ downloaded: {url}")
            return resp.content, mime
        except Exception as e:
            print(f"  ⚠ failed to download {url}: {e}")
            return None, None
    else:
        clean = url.split("?")[0].split("#")[0]
        local_path = os.path.normpath(os.path.join(base_dir, clean))
        if os.path.isfile(local_path):
            try:
                with open(local_path, "rb") as f:
                    content = f.read()
                mime = guess_mime(url)
                print(f"  ⏵ inlined local: {url}")
                return content, mime
            except Exception as e:
                print(f"  ⚠ failed to read {local_path}: {e}")
                return None, None
        else:
            print(f"  ⚠ file not found: {local_path}")
            return None, None


def to_data_uri(content, mime):
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _css_base_for(css_source, fallback_base):
    if not css_source or css_source.startswith("data:"):
        return fallback_base
    if css_source.startswith(("http://", "https://")):
        return css_source.rsplit("/", 1)[0] + "/"
    return os.path.dirname(css_source) or "."


def process_css(css_text, base_dir, css_source=None):
    css_base = _css_base_for(css_source, base_dir)

    def replace_import(match):
        full = match.group(0)
        import_url = match.group(1).strip().strip("\"'")
        if import_url.startswith("data:"):
            return full
        content, mime = fetch(import_url, css_base)
        if content is None:
            return full
        try:
            imported = content.decode("utf-8", errors="replace")
        except Exception:
            return full
        return process_css(imported, css_base, import_url)

    css_text = re.sub(
        r'@import\s+(?:url\(\s*)?["\']?([^"\')\s]+)["\']?\s*\)?[^;]*;',
        replace_import,
        css_text,
    )

    def replace_url(match):
        full = match.group(0)
        url = match.group(1).strip()
        if url.startswith("data:") or url.startswith("#"):
            return full
        content, mime = fetch(url, css_base)
        if content is None:
            return full
        return f'url("{to_data_uri(content, mime)}")'

    css_text = re.sub(
        r'url\(\s*["\']?([^"\')]+)["\']?\s*\)',
        replace_url,
        css_text,
    )
    return css_text


def process_srcset(srcset, base_dir):
    parts = []
    for item in srcset.split(","):
        item = item.strip()
        if not item:
            continue
        tokens = item.split()
        url = tokens[0]
        descriptor = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        if url.startswith("data:"):
            parts.append(item)
            continue
        content, mime = fetch(url, base_dir)
        if content is not None:
            uri = to_data_uri(content, mime)
            parts.append(f"{uri} {descriptor}" if descriptor else uri)
        else:
            parts.append(item)
    return ", ".join(parts)


def make_standalone(html_path):
    html_path = os.path.abspath(html_path)
    base_dir = os.path.dirname(html_path)
    if not os.path.isfile(html_path):
        print(f"ERROR: file not found: {html_path}")
        sys.exit(1)
    print(f"Processing: {html_path}\n")
    with open(html_path, "r", encoding="utf-8-sig", errors="replace") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    for link in soup.find_all("link", rel=True):
        rels = link.get("rel", [])
        if isinstance(rels, str):
            rels = [rels]
        if "stylesheet" not in [r.lower() for r in rels]:
            continue
        href = link.get("href")
        if not href or href.startswith("data:"):
            continue
        content, _ = fetch(href, base_dir)
        if content is None:
            continue
        css_text = content.decode("utf-8", errors="replace")
        css_text = process_css(css_text, base_dir, href)
        style_tag = soup.new_tag("style")
        style_tag.string = css_text
        link.replace_with(style_tag)
    for link in soup.find_all("link", href=True):
        rels = link.get("rel", [])
        if isinstance(rels, str):
            rels = [rels]
        if "stylesheet" in [r.lower() for r in rels]:
            continue
        if any(r.lower() == "manifest" for r in rels):
            continue
        href = link.get("href")
        if not href or href.startswith("data:"):
            continue
        content, mime = fetch(href, base_dir)
        if content is not None:
            link["href"] = to_data_uri(content, mime)
    for script in soup.find_all("script", src=True):
        src = script.get("src")
        if not src or src.startswith("data:"):
            continue
        content, _ = fetch(src, base_dir)
        if content is None:
            continue
        js_text = content.decode("utf-8", errors="replace")
        js_text = re.sub(r"\n?//#\s*sourceMappingURL=.*", "", js_text)
        js_text = re.sub(r"</script", r"<\\/script", js_text, flags=re.IGNORECASE)
        del script["src"]
        script.string = js_text
    for img in soup.find_all("img", src=True):
        src = img.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            img["src"] = to_data_uri(content, mime)
    for tag in soup.find_all(srcset=True):
        tag["srcset"] = process_srcset(tag["srcset"], base_dir)
    for source in soup.find_all("source", src=True):
        src = source.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            source["src"] = to_data_uri(content, mime)
    for video in soup.find_all("video", poster=True):
        poster = video.get("poster")
        if not poster or poster.startswith("data:"):
            continue
        content, mime = fetch(poster, base_dir)
        if content is not None:
            video["poster"] = to_data_uri(content, mime)
    for tag in soup.find_all(["audio", "video"], src=True):
        src = tag.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            tag["src"] = to_data_uri(content, mime)
    for obj in soup.find_all("object", data=True):
        data = obj.get("data")
        if not data or data.startswith("data:"):
            continue
        content, mime = fetch(data, base_dir)
        if content is not None:
            obj["data"] = to_data_uri(content, mime)
    for embed in soup.find_all("embed", src=True):
        src = embed.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            embed["src"] = to_data_uri(content, mime)
    for inp in soup.find_all("input", src=True):
        src = inp.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            inp["src"] = to_data_uri(content, mime)
    for track in soup.find_all("track", src=True):
        src = track.get("src")
        if not src or src.startswith("data:"):
            continue
        content, mime = fetch(src, base_dir)
        if content is not None:
            track["src"] = to_data_uri(content, mime)
    for style in soup.find_all("style"):
        css = style.string
        if not css:
            css = style.get_text()
        if css:
            css = re.sub(r"^\s*<!--\s*", "", css)
            css = re.sub(r"\s*-->\s*$", "", css)
            style.string = process_css(css, base_dir)
    for tag in soup.find_all(style=True):
        val = tag.get("style", "")
        if val:
            tag["style"] = process_css(val, base_dir)
    result = str(soup)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"\n✓ Done — standalone HTML saved to: {html_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python standalone.py <html_file>")
        sys.exit(1)
    make_standalone(sys.argv[1])
