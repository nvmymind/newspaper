"""조선일보 사설 스크래퍼. (RSS 우선, 없으면 Playwright/httpx)"""
import asyncio
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS, parse_rss_to_editorials, RSS_HEADERS

EDITORIAL_LIST_URL = "https://www.chosun.com/opinion/editorial/"
# 오피니언 RSS(사설·칼럼 포함) - 사설만 필터해 사용
CHOSUN_OPINION_RSS = "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml"


async def _fetch_html_playwright(url: str) -> str | None:
    """Playwright로 페이지 렌더 후 HTML 반환. (Chromium 필요: playwright install chromium)"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="load", timeout=30000)
                try:
                    await page.wait_for_selector(
                        "a[href*='/opinion/editorial/']",
                        timeout=15000,
                        state="attached",
                    )
                except Exception:
                    pass
                await asyncio.sleep(1.5)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.0)
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        err = str(e).lower()
        if "executable" in err or "browser" in err or "chromium" in err:
            print("[조선일보] Playwright Chromium 미설치 가능성. 터미널에서: playwright install chromium")
        return None


async def _fetch_html_httpx(url: str) -> str | None:
    """httpx로 HTML 받기 (JS 미렌더링이면 목록이 비어 있을 수 있음)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={**BROWSER_HEADERS, "Referer": "https://www.chosun.com/"},
            timeout=15.0,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
    except Exception:
        return None


def _parse_chosun_page(html: str, source_name: str) -> List[Editorial]:
    """조선일보 목록 HTML 한 페이지에서 사설 추출."""
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.select("a[href*='/opinion/editorial/']"):
        href = item.get("href") or ""
        if not href.startswith("http"):
            href = "https://www.chosun.com" + href
        # URL: /opinion/editorial/YYYY/MM/DD/ID/ 또는 /ID
        m = re.search(r"/editorial/(\d{4})/(\d{2})/(\d{2})/([^/?#]+)", href)
        if not m:
            continue
        art_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        title_el = item.select_one("h2, h3, h4, [class*='title'], [class*='headline']") or item
        title = (title_el.get_text(strip=True) or "").strip()
        if not title or len(title) < 2 or title == "사설":
            parent = item.find_parent(["article", "li", "div"])
            if parent:
                h = parent.select_one("h2, h3, h4, [class*='title'], [class*='headline']")
                if h:
                    title = (h.get_text(strip=True) or "").strip()
        if not title or len(title) < 2:
            continue
        summary = None
        parent = item.find_parent(["article", "li", "div"])
        if parent:
            desc = parent.select_one("p, [class*='desc'], [class*='summary'], [class*='lead']")
            if desc:
                summary = (desc.get_text(strip=True) or "")[:200]
        results.append(
            Editorial(
                source=source_name,
                title=title,
                url=href.split("?")[0],
                summary=summary,
                content=None,
                published_date=art_date,
            )
        )
    return results


class ChosunScraper(BaseScraper):
    source_name = "조선일보"
    list_url = EDITORIAL_LIST_URL
    page_param = "page"
    max_pages = 18  # 12월 등 2~3개월 전 날짜까지 도달
    max_items = 250

    async def fetch_editorials(self) -> List[Editorial]:
        # 1) RSS 우선 시도 (서버에서 Playwright 미설치 시에도 동작)
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, headers=RSS_HEADERS, timeout=20.0
            ) as client:
                r = await client.get(CHOSUN_OPINION_RSS)
                if r.status_code == 200 and r.text.strip():
                    all_items = parse_rss_to_editorials(r.text, self.source_name)
                    # 사설만: 제목에 [사설] 또는 URL에 /opinion/editorial/
                    editorial_only = [
                        e for e in all_items
                        if "[사설]" in (e.title or "") or "/opinion/editorial/" in (e.url or "")
                    ]
                    if editorial_only:
                        seen = set()
                        unique = [e for e in editorial_only if e.url not in seen and not seen.add(e.url)]
                        return unique[: self.max_items]
        except Exception:
            pass

        # 2) 기존 HTML 방식 (Playwright → httpx)
        results: List[Editorial] = []
        for page in range(1, self.max_pages + 1):
            url = self.page_url(page)
            html = await _fetch_html_playwright(url)
            if not html:
                html = await _fetch_html_httpx(url)
            if not html:
                if page == 1:
                    return results
                break
            results.extend(_parse_chosun_page(html, self.source_name))
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        """해당 날짜(YYYY-MM-DD) 사설만 수집. RSS 우선, 없으면 HTML."""
        # RSS로 전체 수집 후 날짜 필터
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, headers=RSS_HEADERS, timeout=20.0
            ) as client:
                r = await client.get(CHOSUN_OPINION_RSS)
                if r.status_code == 200 and r.text.strip():
                    all_items = parse_rss_to_editorials(r.text, self.source_name)
                    editorial_only = [
                        e for e in all_items
                        if ("[사설]" in (e.title or "") or "/opinion/editorial/" in (e.url or ""))
                        and e.published_date == target_date
                    ]
                    if editorial_only:
                        seen = set()
                        return [e for e in editorial_only if e.url not in seen and not seen.add(e.url)]
        except Exception:
            pass

        results: List[Editorial] = []
        for page in range(1, self.max_pages + 1):
            url = self.page_url(page)
            html = await _fetch_html_playwright(url)
            if not html:
                html = await _fetch_html_httpx(url)
            if not html:
                if page == 1:
                    return results
                break
            passed_target = False
            for e in _parse_chosun_page(html, self.source_name):
                if e.published_date < target_date:
                    passed_target = True
                    continue
                if e.published_date == target_date:
                    results.append(e)
            if passed_target:
                break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)]
