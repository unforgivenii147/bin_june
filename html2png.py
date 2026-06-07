#!/data/data/com.termux/files/usr/bin/python

import asyncio
import sys
from pathlib import Path

from pyppeteer import launch


async def main():
    url = sys.argv[1]
    outfile = str(Path(url).with_suffix(".png"))
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    await page.screenshot({"path": outfile})
    await browser.close()


asyncio.get_event_loop().run_until_complete(main())
