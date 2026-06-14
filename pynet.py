#!/data/data/com.termux/files/usr/bin/python

"""
Network State Script
Displays your public IP, local IP, primary/secondary DNS, and approximate internet speed.
"""

import json
import os
import platform
import random
import socket
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request


def get_public_ip():
    """Try multiple public IP services, return the first successful result."""
    services = [
        ("https://api.ipify.org?format=json", "ip"),
        ("https://ipinfo.io/json", "ip"),
        ("https://httpbin.org/ip", "origin"),
        ("http://ip-api.com/json", "query"),
    ]
    for url, key in services:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                ip = data.get(key)
                if ip:
                    return ip
        except Exception:
            continue
    return None


def get_local_ip():
    """Return the primary local IP address by connecting to a remote server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def get_dns_servers():
    """Extract DNS server IPs from the OS configuration."""
    dns_list = []
    system = platform.system()

    try:
        if system:
            with open("/data/data/com.termux/files/usr/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns_list.append(parts[1])
    except Exception as e:
        return [f"Error retrieving DNS: {e}"]

    seen = set()
    unique_dns = []
    for ip in dns_list:
        if ip not in seen:
            seen.add(ip)
            unique_dns.append(ip)
    return unique_dns


def test_speed() -> tuple[float | None, float | None, str | None, str | None]:
    """
    Approximate download/upload speed using HTTP.
    Returns: (download_mbps, upload_mbps, dl_error, ul_error)
    """
    download_url = "http://speedtest.tele2.net/5MB.zip"
    upload_url = "http://httpbin.org/post"

    dl_mbps = None
    ul_mbps = None
    dl_error = None
    ul_error = None

    print("    Testing download speed...")
    try:
        start = time.time()
        with urllib.request.urlopen(download_url, timeout=20) as resp:
            data = resp.read()
        elapsed = time.time() - start
        size_bits = len(data) * 8
        dl_mbps = (size_bits / elapsed) / 1e6
    except Exception as e:
        dl_error = str(e)

    print("    Testing upload speed...")
    try:
        upload_bytes = 1 * 1024 * 1024

        rand_data = "".join(random.choices(string.ascii_letters + string.digits, k=upload_bytes)).encode()

        boundary = "----------ThIs_Is_tHe_bouNdaRY_$"
        body = (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="test.bin"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode() +
            rand_data +
            f"\r\n--{boundary}--\r\n".encode()
        )

        req = urllib.request.Request(upload_url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

        start = time.time()
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        elapsed = time.time() - start
        upload_bits = upload_bytes * 8
        ul_mbps = (upload_bits / elapsed) / 1e6
    except Exception as e:
        ul_error = str(e)

    return dl_mbps, ul_mbps, dl_error, ul_error


def main() -> None:
    print("=" * 50)
    print(" NETWORK STATES ")
    print("=" * 50)

    print("\n[*] Public IP:")
    pub_ip = get_public_ip()
    if pub_ip:
        print(f"    {pub_ip}")
    else:
        print("    Could not determine public IP.")

    print("\n[*] Local IP (primary interface):")
    local_ip = get_local_ip()
    print(f"    {local_ip}")

    print("\n[*] DNS Servers:")
    dns = get_dns_servers()
    if dns:
        for i, server in enumerate(dns, 1):
            if i <= 2:
                print(f"    DNS {i}: {server}")
        if len(dns) > 2:
            print(f"    (plus {len(dns) - 2} more)")
    else:
        print("    No DNS servers found.")


"""
    # --- Internet Speed ---
    print("\n[*] Internet Speed Test:")
    # Try using the official speedtest-cli if available (much more accurate)
    try:
        import speedtest
        print("    Using speedtest-cli...")
        st = speedtest.Speedtest()
        st.get_best_server()
        dl_speed = st.download() / 1e6   # Mbps
        ul_speed = st.upload() / 1e6     # Mbps
        print(f"    Download: {dl_speed:.2f} Mbps")
        print(f"    Upload:   {ul_speed:.2f} Mbps")
    except ImportError:
        # Fallback to built‑in HTTP test
        dl, ul, dl_err, ul_err = test_speed()
        if dl is not None:
            print(f"    Download: {dl:.2f} Mbps (approx.)")
        else:
            print(f"    Download test failed: {dl_err}")
        if ul is not None:
            print(f"    Upload:   {ul:.2f} Mbps (approx.)")
        else:
            print(f"    Upload test failed: {ul_err}")
        print("    (Install 'speedtest-cli' for more reliable results: pip install speedtest-cli)")

    print("\n" + "=" * 50)


"""


if __name__ == "__main__":
    main()
