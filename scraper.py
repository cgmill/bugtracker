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
from pathlib import Path


# Setup 
DOMAIN = 'issues.chromium.org'
CHROMIUM_ISSUES_URL = "https://issues.chromium.org/issues"
SEARCH_QUERY = "?q=status:open"
OUTPUT_DIR = 'scraped_data'

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
async def fetch_new_issues(db, p):
    url = CHROMIUM_ISSUES_URL + SEARCH_QUERY
    print(f"Issue URL: {url}")


    headers = generate_dynamic_headers()
    browser = await p.chromium.launch(channel='chrome', headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_viewport_size({"width":1920, "height":1080})
    await page.set_extra_http_headers(headers)

    try:
        await page.goto(url, timeout=60000, wait_until='networkidle')
        content = await page.content()


    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

    await save_html(url, content)
    issues = await extract_issues(content)
    await save_issues(db, issues)
    return

async def save_html(url, content):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{url.replace('/', '_').replace(':', '_').replace('?', '_').replace('&', '_')}"
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    html_path = output_dir / f'{filename}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved HTML content to {html_path}")

async def extract_issues(content):
    soup = BeautifulSoup(content, 'html.parser')

    issue_rows = soup.find_all('tr', class_='unread')
    issues = []

    for row in issue_rows:
        issue_id = row.get('data-row-id')
        title_link = row.find('a', class_='row-issue-title')

        if title_link:
            url = f"https://issues.chromium.org{title_link['href']}"
            title = title_link.get('title')
            issues.append({
                'issue_id': issue_id,
                'url': url,
                'title': title
            })

    return issues

async def save_issues(db, issues):
    for issue in issues:
        await db.execute('INSERT OR IGNORE INTO issues (id, url, title) VALUES (?, ?, ?)', (issue['issue_id'], issue['url'], issue['title']))
        await db.commit()


async def init_db():
    db = await aiosqlite.connect('scraped_issues.db')
    await db.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            url TEXT,
            title TEXT
        )
    ''')
    await db.commit()
    return db
async def main():
    db = await init_db()

    async with async_playwright() as p:
        await fetch_open_issues(p)
        await fetch_new_issues(db, p)

    await db.close()
    return
if __name__ == '__main__':
    asyncio.run(main())