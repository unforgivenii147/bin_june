#!/data/data/com.termux/files/home/.local/bin/python
import os
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from tqdm import tqdm

# Core settings mimicking the default behavior of Ghost Downloader 3
DEFAULT_CHUNKS = 8
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Ghost-CLI: A lightweight multi-threaded concurrent download manager.")
    parser.add_argument("url", help="The direct file HTTP/HTTPS URL to download")
    parser.add_argument("-o", "--output", help="Output file path or filename")
    parser.add_argument(
        "-c",
        "--chunks",
        type=int,
        default=DEFAULT_CHUNKS,
        help=f"Number of parallel chunk threads (default: {DEFAULT_CHUNKS})",
    )
    parser.add_argument(
        "-ua",
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="Custom User-Agent to emulate browser fingerprints and bypass restrictions",
    )
    return parser.parse_args()


def download_chunk(url, start_byte, end_byte, chunk_id, headers, filename):
    chunk_headers = headers.copy()
    chunk_headers["Range"] = f"bytes={start_byte}-{end_byte}"

    # Stream the chunk file directly to disk to minimize memory footprint
    part_filename = f"{filename}.part{chunk_id}"

    with requests.get(url, headers=chunk_headers, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(part_filename, "wb") as f:
            for data in r.iter_content(chunk_size=1024 * 64):  # 64KB blocks
                if data:
                    f.write(data)
    return part_filename, start_byte


def main():
    args = parse_args()
    url = args.url
    num_chunks = args.chunks

    headers = {"User-Agent": args.user_agent, "Accept": "*/*", "Connection": "keep-alive"}

    # Send a HEAD request to extract details about file capacity and range support
    try:
        head_response = requests.head(url, headers=headers, allow_redirects=True, timeout=15)
        head_response.raise_for_status()
    except requests.RequestException as e:
        print(f"[-] Error reaching target URL: {e}")
        sys.exit(1)

    total_size = int(head_response.headers.get("content-length", 0))
    accept_ranges = head_response.headers.get("accept-ranges", "bytes")

    # Identify proper filename
    if args.output:
        filename = args.output
    else:
        filename = url.split("/")[-1].split("?")[0] or "downloaded_file"

    if total_size == 0:
        print("[-] Warning: Web Server did not return a content length. Falling back to single-stream download.")
        num_chunks = 1

    if accept_ranges != "bytes" and num_chunks > 1:
        print("[-] Target server does not support byte-range slicing. Falling back to single-stream download.")
        num_chunks = 1

    print(f"[*] Target File: {filename}")
    print(f"[*] File Size: {total_size / (1024 * 1024):.2f} MB" if total_size else "[*] File Size: Unknown")
    print(f"[*] Thread Slices: {num_chunks}")

    # Fallback path for streams that do not support multi-threaded slicing
    if num_chunks == 1:
        with (
            requests.get(url, headers=headers, stream=True, timeout=30) as r,
            open(filename, "wb") as f,
            tqdm(total=total_size, unit="B", unit_scale=True, desc=filename) as pbar,
        ):
            for data in r.iter_content(chunk_size=1024 * 64):
                f.write(data)
                pbar.update(len(data))
        print(f"[+] Download complete: {filename}")
        return

    # Calculate individual segment layouts
    chunk_size = total_size // num_chunks
    futures = []
    part_files = [None] * num_chunks

    print("[*] Slicing chunks and initializing network connections...")

    # Global tracking dynamic bar
    with tqdm(total=total_size, unit="B", unit_scale=True, desc="Downloading") as pbar:
        with ThreadPoolExecutor(max_workers=num_chunks) as executor:
            for i in range(num_chunks):
                start_byte = i * chunk_size
                # Assign remainder bytes to final thread chunk
                end_byte = total_size - 1 if i == num_chunks - 1 else (start_byte + chunk_size - 1)

                futures.append(executor.submit(download_chunk, url, start_byte, end_byte, i, headers, filename))

            # Keep tabs on individual file fragments as workers report back
            for future in as_completed(futures):
                try:
                    part_file, start_byte = future.result()
                    # Trace placement indexing from segment names
                    idx = int(part_file.split(".part")[-1])
                    part_files[idx] = part_file

                    # Advance parent progress bar by the chunk scale size
                    actual_part_size = os.path.getsize(part_file)
                    pbar.update(actual_part_size)
                except Exception as e:
                    print(f"\n[-] Critical thread worker exception: {e}")
                    # Clean up partial segments on failure
                    for pf in [f for f in part_files if f and os.path.exists(f)]:
                        os.remove(pf)
                    sys.exit(1)

    # Stitch fragmented data blocks back together
    print("[*] Assembling downloaded slices into final file...")
    with open(filename, "wb") as final_file:
        for part_file in part_files:
            if part_file and os.path.exists(part_file):
                with open(part_file, "rb") as pf:
                    final_file.write(pf.read())
                os.remove(part_file)  # Purge temp part files instantly

    print(f"[+] Download complete and assembled successfully: {filename}")


if __name__ == "__main__":
    main()
