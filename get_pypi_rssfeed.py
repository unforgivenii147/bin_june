#!/data/data/com.termux/files/usr/bin/env python
"""
PyPI RSS Feed Parser
Fetches and extracts newly added packages from the PyPI RSS feed.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import sys
from typing import List, Dict, Optional

# PyPI RSS feed URL for latest packages
PYPI_RSS_URL = "https://pypi.org/rss/packages.xml"


def fetch_rss_feed(url: str) -> Optional[str]:
    """
    Fetch the RSS feed from the given URL.

    Args:
        url: The RSS feed URL

    Returns:
        RSS feed content as string, or None if failed
    """
    try:
        response = requests.get(url, timeout=55)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching RSS feed: {e}", file=sys.stderr)
        return None


def parse_rss_feed(xml_content: str) -> List[Dict[str, str]]:
    """
    Parse the RSS feed XML and extract package information.

    Args:
        xml_content: XML content of the RSS feed

    Returns:
        List of dictionaries containing package information
    """
    packages = []

    try:
        # Parse XML
        root = ET.fromstring(xml_content)

        # RSS feeds have a channel element containing items
        channel = root.find("channel")
        if channel is None:
            print("Error: Invalid RSS format - no channel found", file=sys.stderr)
            return packages

        # Extract items
        items = channel.findall("item")

        for item in items:
            package_info = {
                "title": item.findtext("title", "Unknown"),
                "link": item.findtext("link", "Unknown"),
                "description": item.findtext("description", "No description"),
                "pub_date": item.findtext("pubDate", "Unknown"),
                "guid": item.findtext("guid", "Unknown"),
            }

            # Extract package name from title (usually format: "package-name version")
            title = package_info["title"]
            # Remove version number if present (typically separated by space)
            package_name = title.split()[0] if title else "Unknown"
            package_info["package_name"] = package_name

            packages.append(package_info)

    except ET.ParseError as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error during parsing: {e}", file=sys.stderr)

    return packages


def display_packages(packages: List[Dict[str, str]], limit: Optional[int] = None):
    """
    Display package information in a formatted way.

    Args:
        packages: List of package information dictionaries
        limit: Maximum number of packages to display (None for all)
    """
    if not packages:
        print("No packages found in the RSS feed.")
        return

    # Apply limit if specified
    display_packages = packages[:limit] if limit else packages

    print(f"\n{'=' * 80}")
    print(f"PyPI Latest Packages (Total: {len(packages)}, Showing: {len(display_packages)})")
    print(f"Fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    for i, pkg in enumerate(display_packages, 1):
        print(f"Package #{i}:")
        print(f"  Name:        {pkg['package_name']}")
        print(f"  Full Title:  {pkg['title']}")
        print(f"  Link:        {pkg['link']}")
        print(f"  Published:   {pkg['pub_date']}")
        print(
            f"  Description: {pkg['description'][:100]}..."
            if len(pkg["description"]) > 100
            else f"  Description: {pkg['description']}"
        )
        print(f"  GUID:        {pkg['guid']}")
        print("-" * 80)


def save_to_file(packages: List[Dict[str, str]], filename: str = "pypi_packages.txt"):
    """
    Save extracted packages to a text file.

    Args:
        packages: List of package information dictionaries
        filename: Output filename
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"PyPI Latest Packages - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            for i, pkg in enumerate(packages, 1):
                f.write(f"Package #{i}:\n")
                f.write(f"  Name:        {pkg['package_name']}\n")
                f.write(f"  Full Title:  {pkg['title']}\n")
                f.write(f"  Link:        {pkg['link']}\n")
                f.write(f"  Published:   {pkg['pub_date']}\n")
                f.write(f"  Description: {pkg['description']}\n")
                f.write(f"  GUID:        {pkg['guid']}\n")
                f.write("-" * 80 + "\n")

        print(f"\nPackages saved to '{filename}'")
    except IOError as e:
        print(f"Error saving to file: {e}", file=sys.stderr)


def main():
    """Main function to orchestrate the RSS feed parsing."""

    # Command line arguments for limit and save options
    limit = None
    save_output = False

    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            if limit < 1:
                print("Error: Limit must be a positive number", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            if sys.argv[1] in ["--save", "-s"]:
                save_output = True
            else:
                print("Usage: python script.py [limit] [--save]")
                print("  limit: Number of packages to display (optional)")
                print("  --save or -s: Save output to file")
                sys.exit(1)

    if "--save" in sys.argv or "-s" in sys.argv:
        save_output = True

    print("Fetching PyPI RSS feed...")

    # Fetch RSS feed
    xml_content = fetch_rss_feed(PYPI_RSS_URL)
    if xml_content is None:
        sys.exit(1)

    # Parse RSS feed
    packages = parse_rss_feed(xml_content)

    # Display results
    display_packages(packages, limit)

    # Save to file if requested
    if save_output:
        save_to_file(packages)

    print(f"\nSuccessfully extracted {len(packages)} packages from PyPI RSS feed.")


if __name__ == "__main__":
    main()
