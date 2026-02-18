"""중앙일보 사설 스크래퍼."""
import asyncio
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

LIST_URL = "https://www.joongang.co.kr/opinion/editorial"


async def _fetch_joongang_playwright(url: str) -> str | None:
    """목록이 JS 로드일 때 Playwright로 HTML 수집."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="load", timeout=20000)
                await page.wait_for_selector("a[href*='/article/']", timeout=10000)
                await asyncio.sleep(0.8)
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        return None


def _parse_joongang_html(html: str, source_name: str) -> List[Editorial]:
    """HTML에서 /article/ 링크로 사설 목록 추출."""
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href*='/article/']"):
        href = a.get("href") or ""
        if not href.startswith("http"):
            href = "https://www.joongang.co.kr" + (href if href.startswith("/") else "/" + href)
        href = href.split("?")[0]
        m = re.search(r"/article/(\d{6,})", href)
        if not m:
            continue
        title_el = a.select_one(".headline, .tit, h2, h3, h4, [class*='title']") or a
        title = (title_el.get_text(strip=True) or "").strip()
        if not title or len(title) < 2:
            continue
        parent = a.find_parent(["li", "div", "article", "section"])
        date = None
        if parent:
            pt = parent.get_text()
            for dm in (
                re.search(r"(\d{4})-(\d{2})-(\d{2})", pt),
                re.search(r"(\d{4})\.(\d{2})\.(\d{2})", pt),
                re.search(r"(\d{4})(\d{2})(\d{2})", pt),
            ):
                if dm:
                    date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                    break
        # URL에서 YYYYMMDD 추출 시도 (예: /article/2026021412345)
        if not date:
            url_date = re.search(r"/article/(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d*", href)
            if url_date:
                date = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"
        if not date:
            continue
        results.append(
            Editorial(
                source=source_name,
                title=title,
                url=href,
                summary=None,
                content=None,
                published_date=date,
            )
        )
    return results


class JoongangScraper(BaseScraper):
    source_name = "중앙일보"
    list_url = LIST_URL
    max_pages = 18
    max_items = 250

    async def fetch_editorials(self) -> List[Editorial]:
        results: List[Editorial] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=BROWSER_HEADERS,
            timeout=20.0,
        ) as client:
            for page in range(1, self.max_pages + 1):
                url = self.page_url(page)
                html = None
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    html = r.text
                except Exception:
                    if page == 1:
                        return results
                    break
                if page == 1 and not _parse_joongang_html(html, self.source_name):
                    html = await _fetch_joongang_playwright(url)
                if not html:
                    if page == 1:
                        return results
                    break
                results.extend(_parse_joongang_html(html, self.source_name))
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        """해당 날짜(YYYY-MM-DD) 사설만 수집. 목록이 최신순이므로 그보다 과거가 나오면 중단."""
        results: List[Editorial] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=BROWSER_HEADERS,
            timeout=20.0,
        ) as client:
            for page in range(1, self.max_pages + 1):
                url = self.page_url(page)
                html = None
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    html = r.text
                except Exception:
                    if page == 1:
                        return results
                    break
                if page == 1 and not _parse_joongang_html(html, self.source_name):
                    html = await _fetch_joongang_playwright(url)
                if not html:
                    if page == 1:
                        return results
                    break
                passed_target = False
                for e in _parse_joongang_html(html, self.source_name):
                    if e.published_date < target_date:
                        passed_target = True
                        continue
                    if e.published_date == target_date:
                        results.append(e)
                if passed_target:
                    break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)]
