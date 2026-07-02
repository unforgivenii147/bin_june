#!/data/data/com.termux/files/usr/bin/env python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from pathlib import Path


def read_links_from_file(filename="links.txt"):
    """Read website links from a text file."""
    try:
        with open(filename, "r") as file:
            links = [line.strip() for line in file if line.strip()]
        return links
    except FileNotFoundError:
        print(f"Error: {filename} not found. Please create a {filename} with website URLs.")
        return []


def extract_th18_bases(website_url, timeout=10):
    """
    Extract TH18 base links from a website.
    Looks for common patterns in Clash of Clans base sharing websites.
    """
    th18_links = []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(website_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Find all links on the page
        all_links = soup.find_all("a", href=True)

        for link in all_links:
            href = link.get("href")
            text = link.get_text(strip=True).lower()

            # Look for TH18, Town Hall 18, or similar indicators
            if any(
                indicator in text.lower() or indicator in href.lower()
                for indicator in ["th18", "town hall 18", "townhall 18", "th-18"]
            ):
                # Convert relative URLs to absolute URLs
                absolute_url = urljoin(website_url, href)

                if absolute_url not in th18_links:  # Avoid duplicates
                    th18_links.append({
                        "url": absolute_url,
                        "title": text if text else "TH18 Base",
                        "source": website_url,
                    })

        print(f"✓ Found {len(th18_links)} TH18 bases from {website_url}")

    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching {website_url}: {str(e)}")

    return th18_links


def save_to_html(all_bases, output_file="th18_bases.html"):
    """Save extracted TH18 bases as a clickable HTML file."""

    html_content = (
        """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clash of Clans TH18 Base Links</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            padding: 30px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        
        .info {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-number {
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            color: #999;
            font-size: 12px;
            text-transform: uppercase;
            margin-top: 5px;
        }
        
        .bases-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        
        .base-card {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 5px;
            padding: 15px;
            transition: all 0.3s ease;
        }
        
        .base-card:hover {
            background: #fff;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }
        
        .base-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            word-break: break-word;
        }
        
        .base-link {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-size: 14px;
            margin-bottom: 10px;
            transition: background 0.3s ease;
            word-break: break-all;
        }
        
        .base-link:hover {
            background: #764ba2;
        }
        
        .base-source {
            font-size: 12px;
            color: #999;
            margin-top: 10px;
            word-break: break-word;
        }
        
        .empty {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏰 Clash of Clans TH18 Base Links</h1>
        <p class="info">Extracted and compiled base links from various sources</p>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">"""
        + str(len(all_bases))
        + """</div>
                <div class="stat-label">Total Bases</div>
            </div>
            <div class="stat">
                <div class="stat-number">"""
        + str(len(set(base["source"] for base in all_bases)))
        + """</div>
                <div class="stat-label">Sources</div>
            </div>
        </div>
        
        <div class="bases-grid">
"""
    )

    if all_bases:
        for i, base in enumerate(all_bases, 1):
            html_content += f"""            <div class="base-card">
                <div class="base-title">Base #{i}: {base["title"]}</div>
                <a href="{base["url"]}" class="base-link" target="_blank">🔗 Open Base</a>
                <div class="base-source"><strong>Source:</strong> {base["source"]}</div>
            </div>
"""
    else:
        html_content += """            <div class="empty">
                <p>No TH18 bases found. Make sure your links.txt contains valid URLs and the websites have TH18 bases.</p>
            </div>
"""

    html_content += """        </div>
        
        <div class="footer">
            <p>Generated automatically | Clash of Clans Base Scraper</p>
        </div>
    </div>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✓ HTML file saved as {output_file}")


def main():
    """Main function to orchestrate the scraping process."""
    print("=" * 50)
    print("Clash of Clans TH18 Base Link Extractor")
    print("=" * 50)

    # Read websites from links.txt
    websites = read_links_from_file("links.txt")

    if not websites:
        return

    print(f"\nFound {len(websites)} websites to scrape...\n")

    all_th18_bases = []

    # Scrape each website
    for i, website in enumerate(websites, 1):
        print(f"[{i}/{len(websites)}] Scraping {website}...")

        # Ensure URL has protocol
        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        bases = extract_th18_bases(website)
        all_th18_bases.extend(bases)

        # Be respectful with delays between requests
        time.sleep(1)

    # Save results to HTML
    print(f"\nTotal TH18 bases found: {len(all_th18_bases)}")
    save_to_html(all_th18_bases)
    print("\nDone! Open 'th18_bases.html' in your browser to view the results.")


if __name__ == "__main__":
    main()
