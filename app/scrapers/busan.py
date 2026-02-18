"""부산일보 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

# 부산일보 오피니언/사설: opinionmain, 기사는 view/busan/view.php?code=YYYYMMDD...
LIST_URL = "https://www.busan.com/opinionmain/"
BASE_URL = "https://www.busan.com"


def _parse_busan_html(html: str, source_name: str) -> List[Editorial]:
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href*='view.php'], a[href*='view/busan'], a[href*='code=']"):
        href = (a.get("href") or "").strip()
        if not href or "javascript" in href or "code=" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + href if href.startswith("/") else BASE_URL + "/" + href
        href = href.split("#")[0]
        m = re.search(r"code=(\d{8})\d*", href)
        if not m:
            continue
        date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
        title_el = a.select_one("h2, h3, h4, .tit, .title, [class*='title'], [class*='headline']") or a
        title = (title_el.get_text(strip=True) or "").strip()
        if not title or len(title) < 5:
            continue
        if "[사설]" not in title:
            parent = a.find_parent(["article", "li", "div", "section", "p"])
            if not parent or "[사설]" not in (parent.get_text() or ""):
                continue
        if not title.startswith("[사설]"):
            title = "[사설] " + title
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


class BusanScraper(BaseScraper):
    source_name = "부산일보"
    list_url = LIST_URL
    page_param = None  # URL이 /opinionmain/1/, /opinionmain/2/ 형태일 수 있음
    max_pages = 12
    max_items = 200

    def page_url(self, page: int) -> str:
        if page <= 1:
            return self.list_url.rstrip("/") + "/"
        return self.list_url.rstrip("/") + "/" + str(page) + "/"

    async def fetch_editorials(self) -> List[Editorial]:
        results: List[Editorial] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=BROWSER_HEADERS,
            timeout=20.0,
        ) as client:
            for page in range(1, self.max_pages + 1):
                url = self.page_url(page)
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    results.extend(_parse_busan_html(r.text, self.source_name))
                except Exception:
                    if page == 1:
                        return results
                    break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)][: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        all_ = await self.fetch_editorials()
        return [e for e in all_ if e.published_date == target_date]
