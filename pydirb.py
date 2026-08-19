#!/data/data/com.termux/files/home/.local/bin/python
"""
pydirb — A fast, verbose web content scanner.
Uses pathlib for filesystem operations and asyncio for concurrent requests.

Usage:
    python pydirb.py <url> [options]

Examples:
    python pydirb.py http://example.com -w wordlists/common.txt
    python pydirb.py http://example.com -w wordlists/common.txt -x .php,.html -t 50
    python pydirb.py http://example.com -w wordlists/common.txt -r --recursive-depth 3
    python pydirb.py https://example.com -w wordlists/big.txt -H "Authorization: Bearer xxx" -c "session=abc123"
"""

from __future__ import annotations

import asyncio
import aiohttp
import argparse
import sys
import time
import json
import re
import signal
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from datetime import datetime
from typing import (
    Optional, List, Dict, Set, Tuple, Any, AsyncIterator, Callable
)
from dataclasses import dataclass, field
from enum import Enum
import logging

# ─── Optional: Rich output for colors ───────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn,
        TextColumn, TimeRemainingColumn
    )
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ─── ANSI fallback ──────────────────────────────────────
ANSI = {
    "RED":     "\033[91m",
    "GREEN":   "\033[92m",
    "YELLOW":  "\033[93m",
    "BLUE":    "\033[94m",
    "MAGENTA": "\033[95m",
    "CYAN":    "\033[96m",
    "BOLD":    "\033[1m",
    "DIM":     "\033[2m",
    "RESET":   "\033[0m",
}

# ─── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pydirb")


# ═══════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════

class ResultStatus(Enum):
    FOUND = "FOUND"
    REDIRECT = "REDIRECT"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"

STATUS_MAP: Dict[int, ResultStatus] = {
    200: ResultStatus.FOUND,
    204: ResultStatus.FOUND,
    301: ResultStatus.REDIRECT,
    302: ResultStatus.REDIRECT,
    303: ResultStatus.REDIRECT,
    307: ResultStatus.REDIRECT,
    308: ResultStatus.REDIRECT,
    401: ResultStatus.FORBIDDEN,
    403: ResultStatus.FORBIDDEN,
    404: ResultStatus.NOT_FOUND,
    405: ResultStatus.FORBIDDEN,
    429: ResultStatus.RATE_LIMITED,
    500: ResultStatus.ERROR,
    502: ResultStatus.ERROR,
    503: ResultStatus.ERROR,
}

@dataclass
class ScanResult:
    url: str
    status_code: int
    status: ResultStatus
    content_length: int = 0
    response_time: float = 0.0
    redirect_url: Optional[str] = None
    word: str = ""
    extension: str = ""
    depth: int = 0
    error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    body_snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "status": self.status.value,
            "content_length": self.content_length,
            "response_time_ms": round(self.response_time * 1000, 2),
            "redirect_url": self.redirect_url,
            "word": self.word,
            "extension": self.extension,
            "depth": self.depth,
            "error": self.error,
        }


@dataclass
class ScanConfig:
    base_url: str
    wordlist_path: Path
    extensions: List[str] = field(default_factory=list)
    threads: int = 30
    timeout: int = 10
    recursive: bool = False
    recursive_depth: int = 2
    recursive_status_codes: Set[int] = field(
        default_factory=lambda: {301, 302, 403}
    )
    follow_redirects: bool = False
    include_status_codes: Set[int] = field(default_factory=set)
    exclude_status_codes: Set[int] = field(
        default_factory=lambda: {404}
    )
    include_content_length: Set[int] = field(default_factory=set)
    exclude_content_length: Set[int] = field(default_factory=set)
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    user_agent: str = "pydirb/1.0 (https://github.com/pydirb)"
    http_method: str = "GET"
    delay: float = 0.0
    proxy: Optional[str] = None
    output_file: Optional[str] = None
    output_format: str = "txt"
    verbose: bool = True
    very_verbose: bool = False
    quiet: bool = False
    no_color: bool = False
    save_responses: bool = False
    response_dir: Optional[Path] = None
    stop_on_error: bool = False
    max_retries: int = 2
    prefix: str = ""
    suffix: str = ""
    slash: bool = True
    no_slash: bool = False
    show_all: bool = False
    wildcard_detection: bool = True


# ═══════════════════════════════════════════════════════
#  WORDLIST HANDLER (pathlib-based)
# ═══════════════════════════════════════════════════════

class WordlistLoader:
    """Loads and processes wordlists using pathlib."""

    BUILTIN_WORDLISTS = {
        "common": "admin\nadministrator\nlogin\nwp-admin\ndashboard\nconfig\nbackup\ntest\ndebug\napi\n"
                   "old\nnew\ntmp\ntemp\nprivate\nsecret\nhidden\n.git\n.svn\n.env\nrobots.txt\nsitemap.xml\n"
                   "server-status\nphpinfo.php\ninfo.php\nindex.html\nindex.php\ndefault.html\n"
                   "uploads\nfiles\ndownload\nimages\ncss\njs\nassets\nstatic\nmedia\n"
                   "backup.zip\nbackup.sql\ndatabase.sql\ndb.sql\ndump.sql\n"
                   "wp-config.php\nconfiguration.php\nsettings.php\nconfig.php\n"
                   ".htaccess\n.htpasswd\nweb.config\ncrossdomain.xml\nclientaccesspolicy.xml\n"
                   "readme\nreadme.txt\nreadme.md\nchangelog\nlicense\n",
    }

    @staticmethod
    def load(path: Path, extensions: List[str],
             prefix: str = "", suffix: str = "") -> List[str]:
        """Load wordlist from file or builtin, apply extensions."""
        words: List[str] = []

        if path.name in WordlistLoader.BUILTIN_WORDLISTS:
            words = WordlistLoader.BUILTIN_WORDLISTS[path.name].strip().split("\n")
        elif path.exists() and path.is_file():
            words = WordlistLoader._read_file(path)
        else:
            raise FileNotFoundError(f"Wordlist not found: {path}")

        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique_words: List[str] = []
        for w in words:
            w = w.strip()
            if not w or w.startswith("#"):
                continue
            if w not in seen:
                seen.add(w)
                unique_words.append(w)

        # Generate full path list with extensions
        paths: List[str] = []
        for word in unique_words:
            if extensions:
                for ext in extensions:
                    ext = ext if ext.startswith(".") else f".{ext}"
                    paths.append(f"{prefix}{word}{ext}{suffix}")
            else:
                paths.append(f"{prefix}{word}{suffix}")

        return paths

    @staticmethod
    def _read_file(path: Path) -> List[str]:
        """Read wordlist file using pathlib with encoding detection."""
        encodings = ["utf-8", "latin-1", "ascii", "cp1252"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc).splitlines()
            except (UnicodeDecodeError, OSError):
                continue
        raise IOError(f"Could not read wordlist with any encoding: {path}")

    @staticmethod
    def list_builtin() -> List[str]:
        return list(WordlistLoader.BUILTIN_WORDLISTS.keys())

    @staticmethod
    def count_lines(path: Path) -> int:
        """Count non-empty, non-comment lines in a wordlist."""
        if path.name in WordlistLoader.BUILTIN_WORDLISTS:
            return len([
                l for l in WordlistLoader.BUILTIN_WORDLISTS[path.name].splitlines()
                if l.strip() and not l.startswith("#")
            ])
        count = 0
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip() and not line.startswith("#"):
                count += 1
        return count


# ═══════════════════════════════════════════════════════
#  OUTPUT HANDLER
# ═══════════════════════════════════════════════════════

class OutputHandler:
    """Handles verbose output and result formatting."""

    def __init__(self, config: ScanConfig):
        self.config = config
        self.console = Console(no_color=config.no_color) if RICH_AVAILABLE else None
        self.results: List[ScanResult] = []
        self.start_time: float = 0
        self.total_requests: int = 0
        self.completed_requests: int = 0
        self.found_count: int = 0
        self.error_count: int = 0
        self._lock = asyncio.Lock()
        self._file_handle = None

        if config.output_file:
            self._file_handle = open(config.output_file, "w")

    def color(self, text: str, color: str) -> str:
        if self.config.no_color or not RICH_AVAILABLE:
            return text
        return f"{ANSI.get(color, '')}{text}{ANSI['RESET']}"

    def banner(self):
        banner_text = """
╔══════════════════════════════════════════════════════════════╗
║                        P Y D I R B                            ║
║              Fast Web Content Scanner v1.0                    ║
║         pathlib + asyncio + aiohttp powered                   ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(self.color(banner_text, "CYAN"))

    def print_config(self, config: ScanConfig, word_count: int):
        info_lines = [
            f"  Target URL      : {config.base_url}",
            f"  Wordlist        : {config.wordlist_path} ({word_count} words)",
            f"  Extensions      : {', '.join(config.extensions) or 'none'}",
            f"  Threads         : {config.threads}",
            f"  Timeout         : {config.timeout}s",
            f"  HTTP Method     : {config.http_method}",
            f"  Recursive       : {'yes (depth=' + str(config.recursive_depth) + ')' if config.recursive else 'no'}",
            f"  Follow Redirects: {'yes' if config.follow_redirects else 'no'}",
            f"  User-Agent      : {config.user_agent}",
            f"  Proxy           : {config.proxy or 'none'}",
            f"  Delay           : {config.delay}s",
            f"  Output File     : {config.output_file or 'none'}",
            f"  Verbose         : {'very' if config.very_verbose else 'yes' if config.verbose else 'no'}",
        ]
        print(self.color("┌─ Scan Configuration " + "─" * 38 + "┐", "DIM"))
        for line in info_lines:
            print(self.color("│", "DIM") + line)
        print(self.color("└" + "─" * 58 + "┘", "DIM"))
        print()

    def print_found(self, result: ScanResult):
        """Print a found result with color coding."""
        status = result.status_code
        url = result.url

        if status in (200, 204):
            status_str = self.color(f"[{status}]", "GREEN")
            tag = self.color("FOUND", "GREEN")
        elif status in (301, 302, 303, 307, 308):
            status_str = self.color(f"[{status}]", "BLUE")
            tag = self.color("REDIR", "BLUE")
        elif status in (401, 403, 405):
            status_str = self.color(f"[{status}]", "YELLOW")
            tag = self.color("ACCESS", "YELLOW")
        elif status == 429:
            status_str = self.color(f"[{status}]", "MAGENTA")
            tag = self.color("RATE", "MAGENTA")
        elif status >= 500:
            status_str = self.color(f"[{status}]", "RED")
            tag = self.color("ERROR", "RED")
        else:
            status_str = self.color(f"[{status}]", "DIM")
            tag = self.color("OTHER", "DIM")

        size_str = self.color(f"{result.content_length:>8}b", "DIM")
        time_str = self.color(f"{result.response_time * 1000:>6.1f}ms", "DIM")
        depth_str = self.color(f"d{result.depth}", "DIM") if result.depth > 0 else "   "

        redirect_info = ""
        if result.redirect_url:
            redirect_info = self.color(f" → {result.redirect_url}", "BLUE")

        line = f"  {depth_str} {status_str} {tag}  {size_str} {time_str}  {url}{redirect_info}"
        print(line)

        if self.config.very_verbose and result.body_snippet:
            snippet = result.body_snippet[:200].replace("\n", " ")
            print(self.color(f"         └─ snippet: {snippet}", "DIM"))

    def print_verbose(self, word: str, status: int, url: str):
        """Print verbose info for every request."""
        if status == 404:
            status_str = self.color(f"[{status}]", "DIM")
        elif status in (200, 204):
            status_str = self.color(f"[{status}]", "GREEN")
        elif status in (301, 302, 303, 307, 308):
            status_str = self.color(f"[{status}]", "BLUE")
        else:
            status_str = self.color(f"[{status}]", "YELLOW")
        print(self.color(f"  {status_str}  {url}", "DIM"))

    def print_error(self, url: str, error: str):
        if self.config.verbose:
            print(self.color(f"  {ANSI['RED']}[ERR]{ANSI['RESET']} {url} - {error}", "RED"))

    def print_progress(self, completed: int, total: int, found: int):
        pct = (completed / total * 100) if total > 0 else 0
        bar_len = 30
        filled = int(bar_len * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        elapsed = time.time() - self.start_time
        rate = completed / elapsed if elapsed > 0 else 0
        sys.stdout.write(
            f"\r  {self.color('│', 'DIM')} {bar} {pct:5.1f}% "
            f"| {completed}/{total} | "
            f"{self.color(str(found), 'GREEN')} found | "
            f"{rate:.1f} req/s "
            f"| {elapsed:.1f}s"
        )
        sys.stdout.flush()

    def print_summary(self):
        elapsed = time.time() - self.start_time
        print()
        print(self.color("┌─ Scan Summary " + "─" * 45 + "┐", "CYAN"))

        # Status breakdown
        status_counts: Dict[int, int] = defaultdict(int)
        for r in self.results:
            status_counts[r.status_code] += 1

        print(self.color("│", "CYAN") + f"  Total Requests  : {self.completed_requests}")
        print(self.color("│", "CYAN") + f"  Found          : {self.color(str(self.found_count), 'GREEN')}")
        print(self.color("│", "CYAN") + f"  Errors         : {self.color(str(self.error_count), 'RED')}")
        print(self.color("│", "CYAN") + f"  Time Elapsed   : {elapsed:.2f}s")
        print(self.color("│", "CYAN") + f"  Requests/sec   : {self.completed_requests / elapsed:.1f}" if elapsed > 0 else "")
        print(self.color("│", "CYAN") + "")

        print(self.color("│", "CYAN") + "  Status Code Breakdown:")
        for status in sorted(status_counts.keys()):
            count = status_counts[status]
            if status == 200:
                color = "GREEN"
            elif status in (301, 302, 303, 307, 308):
                color = "BLUE"
            elif status in (401, 403, 405):
                color = "YELLOW"
            elif status == 404:
                color = "DIM"
            else:
                color = "RED"
            bar = "▓" * min(count, 50)
            print(
                self.color("│", "CYAN") +
                f"    {self.color(f'{status}', color)} "
                f"{count:>5}  {bar}"
            )

        print(self.color("│", "CYAN") + "")
        print(self.color("│", "CYAN") + "  Discovered URLs:")
        for r in self.results:
            if r.status in (ResultStatus.FOUND, ResultStatus.REDIRECT, ResultStatus.FORBIDDEN):
                if r.status == ResultStatus.FOUND:
                    marker = self.color("✓", "GREEN")
                elif r.status == ResultStatus.REDIRECT:
                    marker = self.color("→", "BLUE")
                else:
                    marker = self.color("⚠", "YELLOW")
                print(self.color("│", "CYAN") + f"    {marker} {r.url}")

        print(self.color("└" + "─" * 58 + "┘", "CYAN"))

        if self._file_handle:
            self._write_results()
        if self._file_handle:
            self._file_handle.close()

    def _write_results(self):
        if self.config.output_format == "json":
            data = [r.to_dict() for r in self.results]
            json.dump(data, self._file_handle, indent=2)
        else:
            for r in self.results:
                if r.status in (ResultStatus.FOUND, ResultStatus.REDIRECT, ResultStatus.FORBIDDEN):
                    self._file_handle.write(
                        f"{r.status_code}\t{r.content_length}\t{r.url}\n"
                    )

    async def add_result(self, result: ScanResult):
        async with self._lock:
            self.results.append(result)
            self.completed_requests += 1

            if result.status in (ResultStatus.FOUND, ResultStatus.REDIRECT,
                                 ResultStatus.FORBIDDEN):
                self.found_count += 1
                self.print_found(result)
            elif result.status == ResultStatus.ERROR:
                self.error_count += 1
                if self.config.verbose:
                    self.print_error(result.url, result.error or "Unknown error")
            elif self.config.very_verbose:
                self.print_verbose(result.word, result.status_code, result.url)

            if not self.config.quiet and self.completed_requests % 10 == 0:
                self.print_progress(
                    self.completed_requests, self.total_requests, self.found_count
                )

    def close(self):
        if self._file_handle:
            self._file_handle.close()


# ═══════════════════════════════════════════════════════
#  WILDCARD DETECTOR
# ═══════════════════════════════════════════════════════

class WildcardDetector:
    """Detects wildcard responses to eliminate false positives."""

    RANDOM_WORDS = [
        "xqzwkpyjhg", "mnbvcxzlkj", "qazwsxedcrf",
        "plokmijnuhb", "zxcvbnmasdf", "qwertyuiopz",
    ]

    @staticmethod
    async def detect(session: aiohttp.ClientSession,
                     base_url: str, config: ScanConfig) -> Optional[Tuple[int, int]]:
        """
        Send random non-existent paths to detect wildcard responses.
        Returns (status_code, content_length) if wildcard detected, None otherwise.
        """
        results = []
        for word in WildcardDetector.RANDOM_WORDS[:3]:
            url = urljoin(base_url, word)
            try:
                async with session.request(
                    config.http_method, url,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                    allow_redirects=False,
                ) as resp:
                    results.append((resp.status, len(await resp.read())))
            except Exception:
                pass

        if len(results) >= 2:
            statuses = [r[0] for r in results]
            sizes = [r[1] for r in results]
            if len(set(statuses)) == 1 and len(set(sizes)) == 1:
                return (statuses[0], sizes[0])
        return None


# ═══════════════════════════════════════════════════════
#  SCANNER ENGINE
# ═══════════════════════════════════════════════════════

class DirbScanner:
    """Main scanner engine with async concurrency."""

    def __init__(self, config: ScanConfig):
        self.config = config
        self.output = OutputHandler(config)
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.wildcard_info: Optional[Tuple[int, int]] = None
        self.scanned_urls: Set[str] = set()
        self._stop = False
        self.connector: Optional[aiohttp.TCPConnector] = None

    async def scan(self) -> List[ScanResult]:
        """Run the full scan."""
        self.output.start_time = time.time()

        # Load wordlist
        words = WordlistLoader.load(
            self.config.wordlist_path,
            self.config.extensions,
            self.config.prefix,
            self.config.suffix,
        )
        self.output.total_requests = len(words)
        self.output.banner()
        self.output.print_config(self.config, len(words))

        # Setup HTTP session with connection pooling
        self.connector = aiohttp.TCPConnector(
            limit=self.config.threads * 2,
            limit_per_host=self.config.threads * 2,
            ttl_dns_cache=300,
            use_dns_cache=True,
            force_close=False,
            enable_cleanup_closed=True,
        )

        jar = aiohttp.CookieJar(unsafe=True)
        for name, value in self.config.cookies.items():
            jar.update_cookies({name: value})

        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        headers.update(self.config.headers)

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookie_jar=jar,
            headers=headers,
            timeout=timeout,
            trust_env=True,
        ) as session:
            self.session = session
            self.semaphore = asyncio.Semaphore(self.config.threads)

            # Wildcard detection
            if self.config.wildcard_detection:
                print(self.color_msg("  [*] Detecting wildcard responses...", "YELLOW"))
                self.wildcard_info = await WildcardDetector.detect(
                    session, self.config.base_url, self.config
                )
                if self.wildcard_info:
                    wc_status, wc_size = self.wildcard_info
                    print(
                        self.color_msg(
                            f"  [!] Wildcard detected: {wc_status} / {wc_size}b "
                            f"— filtering matching responses",
                            "YELLOW"
                        )
                    )
                else:
                    print(self.color_msg("  [✓] No wildcard response detected", "GREEN"))
                print()

            # Run scan
            print(self.color_msg("  [*] Starting scan...\n", "CYAN"))

            tasks = []
            for word in words:
                if self._stop:
                    break
                task = asyncio.create_task(self._scan_word(word, session, depth=0))
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

            # Recursive scanning
            if self.config.recursive and self.config.recursive_depth > 0:
                await self._recursive_scan(session, words)

        self.output.print_summary()
        return self.output.results

    def color_msg(self, text: str, color: str) -> str:
        return self.output.color(text, color)

    async def _scan_word(self, word: str, session: aiohttp.ClientSession,
                         depth: int = 0, base_url: Optional[str] = None) -> Optional[ScanResult]:
        """Scan a single word/path."""
        if self._stop:
            return None

        async with self.semaphore:
            url_base = base_url or self.config.base_url
            path = word if word.startswith("/") else f"/{word}"
            url = urljoin(url_base, path)

            if url in self.scanned_urls:
                return None
            self.scanned_urls.add(url)

            # Rate limiting delay
            if self.config.delay > 0:
                await asyncio.sleep(self.config.delay)

            result = await self._make_request(session, url, word, depth)

            if result:
                await self.output.add_result(result)

                # Save response if enabled
                if self.config.save_responses and result.status == ResultStatus.FOUND:
                    await self._save_response(result, session)

            return result

    async def _make_request(self, session: aiohttp.ClientSession,
                            url: str, word: str, depth: int) -> Optional[ScanResult]:
        """Make a single HTTP request."""
        retries = 0
        last_error = None

        while retries <= self.config.max_retries:
            try:
                start_time = time.time()
                async with session.request(
                    self.config.http_method,
                    url,
                    allow_redirects=self.config.follow_redirects,
                    ssl=False,
                ) as response:
                    body = await response.read()
                    elapsed = time.time() - start_time

                    status_code = response.status
                    content_length = len(body)

                    # Wildcard filtering
                    if self.wildcard_info:
                        wc_status, wc_size = self.wildcard_info
                        if status_code == wc_status and content_length == wc_size:
                            # Likely wildcard false positive
                            return ScanResult(
                                url=url, status_code=status_code,
                                status=ResultStatus.NOT_FOUND,
                                content_length=content_length,
                                response_time=elapsed,
                                word=word, depth=depth,
                            )

                    # Determine result status
                    result_status = STATUS_MAP.get(status_code, ResultStatus.NOT_FOUND)

                    # Get redirect URL if present
                    redirect_url = None
                    if status_code in (301, 302, 303, 307, 308):
                        redirect_url = response.headers.get("Location", "")

                    # Body snippet for very verbose mode
                    body_snippet = ""
                    if self.config.very_verbose and body:
                        try:
                            body_snippet = body.decode("utf-8", errors="ignore")[:200]
                        except Exception:
                            body_snippet = ""

                    # Collect headers
                    resp_headers = dict(response.headers)

                    result = ScanResult(
                        url=url,
                        status_code=status_code,
                        status=result_status,
                        content_length=content_length,
                        response_time=elapsed,
                        redirect_url=redirect_url,
                        word=word,
                        depth=depth,
                        headers=resp_headers,
                        body_snippet=body_snippet,
                    )

                    # Filter logic
                    if not self._should_report(result):
                        return result

                    return result

            except asyncio.TimeoutError:
                last_error = "Timeout"
                retries += 1
                if retries <= self.config.max_retries:
                    await asyncio.sleep(0.5 * retries)
            except aiohttp.ClientError as e:
                last_error = str(e)
                retries += 1
                if retries <= self.config.max_retries:
                    await asyncio.sleep(0.5 * retries)
            except Exception as e:
                last_error = str(e)
                break

        # All retries exhausted
        result = ScanResult(
            url=url, status_code=0,
            status=ResultStatus.ERROR,
            word=word, depth=depth,
            error=last_error,
        )
        if self.config.verbose:
            await self.output.add_result(result)
        return result

    def _should_report(self, result: ScanResult) -> bool:
        """Determine if a result should be reported based on filters."""
        if self.config.show_all:
            return True

        # Exclude status codes
        if result.status_code in self.config.exclude_status_codes:
            return False

        # Include only specific status codes
        if self.config.include_status_codes and \
           result.status_code not in self.config.include_status_codes:
            return False

        # Exclude by content length
        if result.content_length in self.config.exclude_content_length:
            return False

        # Include only specific content lengths
        if self.config.include_content_length and \
           result.content_length not in self.config.include_content_length:
            return False

        return True

    async def _recursive_scan(self, session: aiohttp.ClientSession,
                              base_words: List[str]):
        """Perform recursive scanning on discovered directories."""
        print(self.color_msg("\n  [*] Starting recursive scan...\n", "CYAN"))

        for depth in range(1, self.config.recursive_depth + 1):
            if self._stop:
                break

            # Find directories to recurse into
            dirs_to_scan = [
                r for r in self.output.results
                if r.status_code in self.config.recursive_status_codes
                and r.depth == depth - 1
            ]

            if not dirs_to_scan:
                break

            print(self.color_msg(
                f"  [*] Recursion depth {depth}: {len(dirs_to_scan)} directories\n",
                "CYAN"
            ))

            tasks = []
            for dir_result in dirs_to_scan:
                # Construct base URL for this directory
                base = dir_result.url.rstrip("/") + "/"
                for word in base_words:
                    if self._stop:
                        break
                    task = asyncio.create_task(
                        self._scan_word(word, session, depth=depth, base_url=base)
                    )
                    tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _save_response(self, result: ScanResult,
                             session: aiohttp.ClientSession):
        """Save response body to file."""
        if not self.config.response_dir:
            return

        self.config.response_dir.mkdir(parents=True, exist_ok=True)

        # Create safe filename from URL
        parsed = urlparse(result.url)
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', parsed.path.strip("/"))
        if not safe_name:
            safe_name = "root"
        filepath = self.config.response_dir / f"{result.status_code}_{safe_name}.html"

        try:
            async with session.get(result.url) as resp:
                body = await resp.read()
                filepath.write_bytes(body)
        except Exception as e:
            logger.warning(f"Could not save response for {result.url}: {e}")

    def stop(self):
        """Stop the scan gracefully."""
        self._stop = True
        print(self.color_msg("\n  [!] Stopping scan...", "YELLOW"))


# ═══════════════════════════════════════════════════════
#  ARGUMENT PARSER
# ═══════════════════════════════════════════════════════

def parse_args() -> ScanConfig:
    parser = argparse.ArgumentParser(
        prog="pydirb",
        description="Fast, verbose web content scanner (dirb in Python)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pydirb http://example.com -w common
  pydirb http://example.com -w /usr/share/wordlists/dirb/common.txt -x .php,.html
  pydirb http://example.com -w common -t 50 -r --recursive-depth 3
  pydirb https://example.com -w big.txt -H "Authorization: Bearer token" --proxy http://127.0.0.1:8080
  pydirb http://example.com -w common --output results.json --output-format json
""",
    )

    parser.add_argument("url", help="Target URL (e.g., http://example.com)")
    parser.add_argument("-w", "--wordlist", default="common",
                        help="Wordlist file path or builtin name (common)")
    parser.add_argument("-x", "--extensions",
                        help="Comma-separated extensions (e.g., .php,.html,.txt)")
    parser.add_argument("-t", "--threads", type=int, default=30,
                        help="Number of concurrent threads (default: 30)")
    parser.add_argument("-to", "--timeout", type=int, default=10,
                        help="Request timeout in seconds (default: 10)")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Enable recursive scanning")
    parser.add_argument("--recursive-depth", type=int, default=2,
                        help="Maximum recursion depth (default: 2)")
    parser.add_argument("-f", "--follow-redirects", action="store_true",
                        help="Follow HTTP redirects")
    parser.add_argument("-H", "--header", action="append", default=[],
                        help="Custom header (format: 'Key: Value')")
    parser.add_argument("-c", "--cookie", action="append", default=[],
                        help="Cookie (format: name=value)")
    parser.add_argument("-a", "--user-agent",
                        help="Custom User-Agent string")
    parser.add_argument("-m", "--method", default="GET",
                        choices=["GET", "HEAD", "POST", "OPTIONS", "PUT"],
                        help="HTTP method (default: GET)")
    parser.add_argument("-d", "--delay", type=float, default=0,
                        help="Delay between requests in seconds (default: 0)")
    parser.add_argument("--proxy", help="HTTP proxy URL")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--output-format", default="txt",
                        choices=["txt", "json"],
                        help="Output format (default: txt)")
    parser.add_argument("-v", "--verbose", action="store_true", default=True,
                        help="Verbose output (default: on)")
    parser.add_argument("-vv", "--very-verbose", action="store_true",
                        help="Very verbose output (show all requests)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode (minimal output)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")
    parser.add_argument("--save-responses", help="Save response bodies to directory")
    parser.add_argument("--include-status", help="Only show these status codes (comma-separated)")
    parser.add_argument("--exclude-status", help="Exclude these status codes (comma-separated)")
    parser.add_argument("--exclude-size", help="Exclude responses of this size (comma-separated)")
    parser.add_argument("--no-wildcard", action="store_true",
                        help="Disable wildcard detection")
    parser.add_argument("--show-all", action="store_true",
                        help="Show all results (no filtering)")
    parser.add_argument("--prefix", default="",
                        help="Prefix to add to all words")
    parser.add_argument("--suffix", default="",
                        help="Suffix to add to all words")
    parser.add_argument("--max-retries", type=int, default=2,
                        help="Max retries per request (default: 2)")
    parser.add_argument("--list-wordlists", action="store_true",
                        help="List builtin wordlists and exit")

    args = parser.parse_args()

    if args.list_wordlists:
        print("Builtin wordlists:")
        for name in WordlistLoader.list_builtin():
            count = WordlistLoader.count_lines(Path(name))
            print(f"  {name} ({count} entries)")
        sys.exit(0)

    # Parse extensions
    extensions = []
    if args.extensions:
        extensions = [e.strip() if e.strip().startswith(".") else f".{e.strip()}"
                      for e in args.extensions.split(",")]

    # Parse headers
    headers = {}
    for h in args.header:
        if ":" in h:
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

    # Parse cookies
    cookies = {}
    for c in args.cookie:
        if "=" in c:
            key, value = c.split("=", 1)
            cookies[key.strip()] = value.strip()

    # Parse status filters
    include_status = set()
    if args.include_status:
        include_status = {int(s) for s in args.include_status.split(",")}

    exclude_status = {404}
    if args.exclude_status:
        exclude_status = {int(s) for s in args.exclude_status.split(",")}

    exclude_size = set()
    if args.exclude_size:
        exclude_size = {int(s) for s in args.exclude_size.split(",")}

    # Ensure URL has scheme
    url = args.url
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"

    # Resolve wordlist path
    wordlist_path = Path(args.wordlist)
    if not wordlist_path.exists() and args.wordlist in WordlistLoader.list_builtin():
        wordlist_path = Path(args.wordlist)

    response_dir = Path(args.save_responses) if args.save_responses else None

    config = ScanConfig(
        base_url=url,
        wordlist_path=wordlist_path,
        extensions=extensions,
        threads=args.threads,
        timeout=args.timeout,
        recursive=args.recursive,
        recursive_depth=args.recursive_depth,
        follow_redirects=args.follow_redirects,
        headers=headers,
        cookies=cookies,
        user_agent=args.user_agent or "pydirb/1.0 (https://github.com/pydirb)",
        http_method=args.method,
        delay=args.delay,
        proxy=args.proxy,
        output_file=args.output,
        output_format=args.output_format,
        verbose=args.verbose,
        very_verbose=args.very_verbose,
        quiet=args.quiet,
        no_color=args.no_color,
        save_responses=bool(args.save_responses),
        response_dir=response_dir,
        include_status_codes=include_status,
        exclude_status_codes=exclude_status,
        exclude_content_length=exclude_size,
        wildcard_detection=not args.no_wildcard,
        show_all=args.show_all,
        prefix=args.prefix,
        suffix=args.suffix,
        max_retries=args.max_retries,
    )

    return config


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

async def async_main():
    config = parse_args()
    scanner = DirbScanner(config)

    # Handle Ctrl+C
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        scanner.stop()
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        await scanner.scan()
    except KeyboardInterrupt:
        scanner.stop()
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise
    finally:
        scanner.output.close()


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(async_main())


# ═══════════════════════════════════════════════════════
#  TESTS
# ═══════════════════════════════════════════════════════

def run_tests():
    """Run unit tests for pydirb components."""
    import tempfile
    import os

    print("\n" + "=" * 60)
    print("  🧪 pydirb Unit Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    def assert_eq(actual, expected, name):
        nonlocal passed, failed
        if actual == expected:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name}: expected {expected}, got {actual}")
            failed += 1

    # Test 1: WordlistLoader with builtin
    print("\n[Test 1] WordlistLoader - builtin wordlist")
    words = WordlistLoader.load(Path("common"), [])
    assert_eq(len(words) > 0, True, "Builtin wordlist loads")
    assert_eq("admin" in words, True, "Contains 'admin'")
    assert_eq("wp-admin" in words, True, "Contains 'wp-admin'")

    # Test 2: WordlistLoader with extensions
    print("\n[Test 2] WordlistLoader - extensions")
    words_ext = WordlistLoader.load(Path("common"), [".php", ".html"])
    assert_eq(any(w.endswith(".php") for w in words_ext), True, "Has .php extensions")
    assert_eq(any(w.endswith(".html") for w in words_ext), True, "Has .html extensions")

    # Test 3: WordlistLoader with file
    print("\n[Test 3] WordlistLoader - file reading")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("# comment line\n")
        f.write("test1\n")
        f.write("test2\n")
        f.write("\n")  # empty line
        f.write("test3\n")
        temp_path = f.name

    try:
        file_words = WordlistLoader.load(Path(temp_path), [])
        assert_eq(len(file_words), 3, "Skips comments and empty lines")
        assert_eq(file_words, ["test1", "test2", "test3"], "Correct word order")
    finally:
        os.unlink(temp_path)

    # Test 4: WordlistLoader deduplication
    print("\n[Test 4] WordlistLoader - deduplication")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("dup\n")
        f.write("dup\n")
        f.write("dup\n")
        f.write("unique\n")
        temp_path = f.name

    try:
        dedup_words = WordlistLoader.load(Path(temp_path), [])
        assert_eq(len(dedup_words), 2, "Removes duplicates")
        assert_eq(dedup_words, ["dup", "unique"], "Preserves order after dedup")
    finally:
        os.unlink(temp_path)

    # Test 5: WordlistLoader with prefix/suffix
    print("\n[Test 5] WordlistLoader - prefix/suffix")
    ps_words = WordlistLoader.load(Path("common"), [], prefix="api/", suffix="/")
    assert_eq(any(w.startswith("api/") for w in ps_words), True, "Prefix applied")
    assert_eq(any(w.endswith("/") for w in ps_words), True, "Suffix applied")

    # Test 6: ScanResult dataclass
    print("\n[Test 6] ScanResult - dataclass")
    result = ScanResult(
        url="http://example.com/admin",
        status_code=200,
        status=ResultStatus.FOUND,
        content_length=1234,
        response_time=0.05,
        word="admin",
    )
    d = result.to_dict()
    assert_eq(d["url"], "http://example.com/admin", "URL correct")
    assert_eq(d["status"], "FOUND", "Status correct")
    assert_eq(d["content_length"], 1234, "Content length correct")

    # Test 7: STATUS_MAP
    print("\n[Test 7] STATUS_MAP - status code mapping")
    assert_eq(STATUS_MAP[200], ResultStatus.FOUND, "200 -> FOUND")
    assert_eq(STATUS_MAP[301], ResultStatus.REDIRECT, "301 -> REDIRECT")
    assert_eq(STATUS_MAP[404], ResultStatus.NOT_FOUND, "404 -> NOT_FOUND")
    assert_eq(STATUS_MAP[403], ResultStatus.FORBIDDEN, "403 -> FORBIDDEN")
    assert_eq(STATUS_MAP[429], ResultStatus.RATE_LIMITED, "429 -> RATE_LIMITED")

    # Test 8: WildcardDetector random words
    print("\n[Test 8] WildcardDetector - random words exist")
    assert_eq(len(WildcardDetector.RANDOM_WORDS) >= 3, True, "Has 3+ random words")
    assert_eq(all(len(w) > 5 for w in WildcardDetector.RANDOM_WORDS), True,
              "Random words are long enough")

    # Test 9: ScanConfig defaults
    print("\n[Test 9] ScanConfig - default values")
    config = ScanConfig(base_url="http://test.com", wordlist_path=Path("common"))
    assert_eq(config.threads, 30, "Default threads = 30")
    assert_eq(config.timeout, 10, "Default timeout = 10")
    assert_eq(config.http_method, "GET", "Default method = GET")
    assert_eq(config.recursive, False, "Default recursive = False")
    assert_eq(404 in config.exclude_status_codes, True, "404 excluded by default")

    # Test 10: WordlistLoader count_lines
    print("\n[Test 10] WordlistLoader - count_lines")
    count = WordlistLoader.count_lines(Path("common"))
    assert_eq(count > 0, True, "Builtin wordlist has entries")

    # Test 11: pathlib Path operations
    print("\n[Test 11] pathlib - Path operations")
    p = Path("/tmp") / "wordlists" / "common.txt"
    assert_eq(str(p), "/tmp/wordlists/common.txt", "Path join works")
    assert_eq(p.suffix, ".txt", "Suffix extraction works")
    assert_eq(p.stem, "common", "Stem extraction works")

    # Test 12: OutputHandler color
    print("\n[Test 12] OutputHandler - color formatting")
    config_no_color = ScanConfig(
        base_url="http://test.com",
        wordlist_path=Path("common"),
        no_color=True,
    )
    out = OutputHandler(config_no_color)
    assert_eq(out.color("test", "RED"), "test", "No color when disabled")

    # Summary
    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("  ✅ All tests passed!")
    else:
        print(f"  ❌ {failed} test(s) failed!")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        sys.exit(0 if run_tests() else 1)
    main()
