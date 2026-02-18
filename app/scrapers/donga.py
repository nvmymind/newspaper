"""동아일보 사설 스크래퍼. (목록이 JS 렌더링이라 Playwright 우선)"""
import asyncio
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

LIST_URL = "https://www.donga.com/news/List/700401"  # 사설/칼럼 PC
LIST_URL_MOBILE = "https://www.donga.com/news/m/List_0401"  # 모바일 (서버 렌더일 수 있음)


async def _fetch_html_playwright(url: str) -> str | None:
    """Playwright로 페이지 렌더 후 HTML 반환. 동아일보 목록은 JS 로드라 브라우저 필요."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                # 목록/제목 로딩 대기 (선택자 실패해도 계속 진행)
                try:
                    await page.wait_for_selector("h4, a[href*='article'], [class*='tit'], [class*='title']", timeout=10000)
                except Exception:
                    pass
                await asyncio.sleep(1.5)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.8)
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        return None


async def _fetch_html_httpx(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={**BROWSER_HEADERS, "Referer": "https://www.donga.com/"},
            timeout=15.0,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
    except Exception:
        return None


# 동아일보 기사 URL: https://www.donga.com/news/섹션/article/all/YYYYMMDD/ID/페이지
_DATE_IN_URL = re.compile(r"/article/all/(\d{4})(\d{2})(\d{2})/", re.I)
_DATE_IN_URL_ALT = re.compile(r"/(\d{4})(\d{2})(\d{2})/\d+", re.I)  # /YYYYMMDD/숫자


def _parse_donga_page(html: str, source_name: str) -> List[Editorial]:
    """동아일보 목록 HTML에서 사설만 추출. [사설] 제목 또는 article/all/ 날짜 링크 기준."""
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set[str] = set()

    def add_editorial(href: str, title: str, date: str) -> None:
        href = href.split("?")[0]
        if href in seen_urls:
            return
        if not title.startswith("[사설]"):
            title = "[사설] " + title.lstrip()
        seen_urls.add(href)
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

    # 1) [사설]이 들어 있는 제목 요소 → 부모/조상 <a>에서 href 추출
    for tag in soup.find_all(["h2", "h3", "h4", "h5", "a"]):
        text = (tag.get_text(strip=True) or "").strip()
        if "[사설]" not in text or len(text) < 10:
            continue
        a = tag if tag.name == "a" else tag.find_parent("a")
        if not a or not a.get("href"):
            continue
        href = (a.get("href") or "").strip()
        if "javascript" in href or not href:
            continue
        if not href.startswith("http"):
            href = "https://www.donga.com" + href if href.startswith("/") else "https://www.donga.com/" + href
        m = _DATE_IN_URL.search(href) or _DATE_IN_URL_ALT.search(href)
        if not m:
            continue
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        add_editorial(href, text, date)

    # 2) 기존 방식: article/all/ 또는 /news/.../ 날짜 링크 + 블록에 [사설] 포함
    for a in soup.select("a[href*='article'], a[href*='/news/']"):
        href = (a.get("href") or "").strip()
        if not href or "javascript" in href or href in seen_urls:
            continue
        if not href.startswith("http"):
            href = "https://www.donga.com" + href if href.startswith("/") else "https://www.donga.com/" + href
        m = _DATE_IN_URL.search(href) or _DATE_IN_URL_ALT.search(href)
        if not m:
            continue
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        title = (a.get_text(strip=True) or "").strip()
        if len(title) < 5:
            parent = a.find_parent(["article", "li", "div", "section"])
            if parent:
                h = parent.select_one("h2, h3, h4, h5, [class*='title'], [class*='headline']")
                if h:
                    title = (h.get_text(strip=True) or "").strip()
        if not title or len(title) < 5:
            continue
        block = a.find_parent(["article", "li", "div", "section"])
        block_text = (block.get_text() if block else "") + " " + title
        if "[사설]" not in block_text and not title.startswith("[사설]"):
            continue
        add_editorial(href, title, date)

    return results


class DongaScraper(BaseScraper):
    source_name = "동아일보"
    list_url = LIST_URL
    page_param = "p"
    max_pages = 18
    max_items = 250

    async def fetch_editorials(self) -> List[Editorial]:
        results: List[Editorial] = []
        use_mobile = None
        for page in range(1, self.max_pages + 1):
            url = self.page_url(page)
            if page == 1:
                # 모바일이 서버 렌더일 수 있어 먼저 시도
                html = await _fetch_html_httpx(LIST_URL_MOBILE)
                if html and _parse_donga_page(html, self.source_name):
                    use_mobile = True
                if not html or not use_mobile:
                    html = await _fetch_html_playwright(url) or html or await _fetch_html_httpx(url)
                if not html:
                    return []
            elif use_mobile:
                url = LIST_URL_MOBILE + ("?" + self.page_param + "=" + str(page) if page > 1 else "")
                html = await _fetch_html_httpx(url)
            else:
                html = await _fetch_html_playwright(url) or await _fetch_html_httpx(url)
            if not html:
                if page == 1:
                    return []
                break
            results.extend(_parse_donga_page(html, self.source_name))
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        """해당 날짜(YYYY-MM-DD) 사설만 수집. 목록이 최신순이므로 그보다 과거가 나오면 중단."""
        results: List[Editorial] = []
        use_mobile = None
        for page in range(1, self.max_pages + 1):
            url = self.page_url(page)
            if page == 1:
                for attempt in range(2):  # 1페이지 실패 시 1회 재시도
                    html = await _fetch_html_httpx(LIST_URL_MOBILE)
                    if html and _parse_donga_page(html, self.source_name):
                        use_mobile = True
                        break
                    if not html or not use_mobile:
                        html = await _fetch_html_playwright(url) or html or await _fetch_html_httpx(url)
                    if html and _parse_donga_page(html, self.source_name):
                        break
                    if attempt == 0:
                        await asyncio.sleep(1.0)  # 재시도 전 잠시 대기
                if not html:
                    return results
            elif use_mobile:
                url = LIST_URL_MOBILE + ("?" + self.page_param + "=" + str(page) if page > 1 else "")
                html = await _fetch_html_httpx(url)
            else:
                html = await _fetch_html_playwright(url) or await _fetch_html_httpx(url)
            if not html:
                if page == 1:
                    return results
                break
            passed_target = False
            for e in _parse_donga_page(html, self.source_name):
                if e.published_date < target_date:
                    passed_target = True
                    continue
                if e.published_date == target_date:
                    results.append(e)
            if passed_target:
                break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)]
