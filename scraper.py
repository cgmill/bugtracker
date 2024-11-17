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
from urllib.parse import urlparse
from urllib.parse import parse_qs
from time import sleep


# Setup 
DOMAIN = 'issues.chromium.org'
CHROMIUM_ISSUES_URL = "https://issues.chromium.org/issues"
FILTERS = [ "status:open", "created>2024-11-15" ] # Get a reasonable number of issues for now
OUTPUT_DIR = 'scraped_data'
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')



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
    url = CHROMIUM_ISSUES_URL + "?q=" + "%20".join(FILTERS)
    print(f"Issue URL: {url}")

    headers = generate_dynamic_headers()
    browser = await p.chromium.launch(channel='chrome', headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_viewport_size({"width":1920, "height":1080})
    await page.set_extra_http_headers(headers)

    await page.goto(url + f"&p={p}", timeout=60000, wait_until='networkidle')
    p = 0
    while p < 50: # get a maximum of 50 pages of issues for testing. should stop before that
        try:
            await page.wait_for_load_state('networkidle')
            content = await page.content()
            await save_raw(url, p, content)
            issues = await extract_issues(content)
            await save_issues(db, issues)
            
            np_button = page.get_by_role("button", name="Go to next page")
            if not await np_button.is_disabled():
                await np_button.click()
            else:
                print("No next page button found, stopping")
                break

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return

        p += 1
    return


async def save_raw(url, p, content):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_new_chromium_issues"
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(exist_ok=True)

    html_path = output_dir / f'{filename}_p{p}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved HTML content to {html_path}")
    return


async def extract_issues(content):
    soup = BeautifulSoup(content, 'html.parser')

    issue_rows = soup.find_all('tr', class_='unread')
    issues = []

    for row in issue_rows:
        issue_id = row.get('data-row-id')
        title_link = row.find('a', class_='row-issue-title')

        if title_link:
            url = f"https://issues.chromium.org/{title_link['href']}"
            title = title_link.get('title')
            issues.append({
                'issue_id': issue_id,
                'url': url,
                'title': title
            })

    return issues


async def save_issues(db, issues):
    for issue in issues:
        await db.execute('INSERT OR IGNORE INTO issues (id, url, title, visible, last_checked) VALUES (?, ?, ?, ?, ?)', (issue['issue_id'], issue['url'], issue['title'], 1, NOW))
        await db.commit()


async def init_db():
    db = await aiosqlite.connect('scraped_issues.db')
    await db.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            visible BOOLEAN,
            last_checked DATETIME
        )
    ''')
    await db.commit()
    return db

async def new_page (p):
    headers = generate_dynamic_headers()
    browser = await p.chromium.launch(channel='chrome', headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.set_viewport_size({"width":1920, "height":1080})
    await page.set_extra_http_headers(headers)
    return page

async def check_issues(db, p):
    past_issues = 'SELECT * FROM issues WHERE visible=1 AND last_checked < ? LIMIT 5' # Limiting to 5 issues for testing
    async with await db.execute(past_issues, (NOW,)) as cursor:
        async for row in cursor:
            url = row[1]
            page = await new_page(p)

            try:
                response = await page.goto(url, timeout=60000, wait_until='load')

            except Exception as e:
                print(f"Error scraping {url}: {e}")
                return []

            if response.ok:
                print(f"Issue {row[0]} is still visible")
            
            await db.execute('UPDATE issues SET visible=?, last_checked=? WHERE id=?', (1 if response.ok else 0, NOW, row[0]))
            await db.commit()

# async def check_issue_status(db, p):          


async def main():
    db = await init_db()
    async with async_playwright() as p:
        await fetch_new_issues(db, p)

#        await check_issues(db, p)

    await db.close()
    return


if __name__ == '__main__':
    asyncio.run(main())
