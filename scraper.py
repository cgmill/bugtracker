import asyncio
import aiohttp
from playwright.async_api import async_playwright
import aiosqlite
import os
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup
import markdown
from icecream import ic
# Setup 
DOMAIN = 'issues.chromium.org'
CHROMIUM_ISSUES_URL = "https://issues.chromium.org/issues"
SEARCH_QUERY = "?q=status:open"
def generate_dynamic_headers():
    """Generate headers dynamically based on URL and timestamp."""
    chrome_version = "130.0.0.0"
    return {
        "sec-ch-ua-platform": '"Windows"',
        "Referer": f"https://issues.chromium.org/",
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36",
        "sec-ch-ua": f'"Chromium";v="{chrome_version.split(".")[0]}", "Google Chrome";v="{chrome_version.split(".")[0]}", "Not?A_Brand";v="99"',
        "DNT": "1",
        "sec-ch-ua-mobile": "?0",
        "Content-Type": "application/json"
    }
# Fetching open issues from Chromium Issue Tracker
async def fetch_open_issues(p):
    url = CHROMIUM_ISSUES_URL + SEARCH_QUERY
    print(f"Issue URL: {url}")


    headers = generate_dynamic_headers()
    browser = await p.chromium.launch(channel='chrome', headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_extra_http_headers(headers)

    try:
        await page.goto(url, timeout=60000, wait_until='networkidle')
        content = await page.content()
        print(content)

    except Exception as e:
        print(f"Error scraping {url}: {e}")
async def main():
    async with async_playwright() as p:
        await fetch_open_issues(p)

    return
if __name__ == '__main__':
    asyncio.run(main())