"""국민일보 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

LIST_URL = "https://www.kmib.co.kr/article/listing.asp?sid1=opi"


def _parse_kmib_html(html: str, source_name: str) -> List[Editorial]:
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href*='view.asp'], a[href*='arcid=']"):
        href = (a.get("href") or "").strip()
        if "arcid=" not in href:
            continue
        if not href.startswith("http"):
            href = "https://www.kmib.co.kr/article/" + href.lstrip("/") if "view.asp" in href or "article" in href else "https://www.kmib.co.kr/" + href.lstrip("/")
        href = href.split("#")[0]
        title_el = a.select_one("h2, h3, h4, .tit, .title, [class*='title']") or a
        title = (title_el.get_text(strip=True) or "").strip()
        if not title or len(title) < 5:
            continue
        if "[사설]" not in title:
            parent = a.find_parent(["li", "div", "article", "section"])
            if not parent or "[사설]" not in (parent.get_text() or ""):
                continue
        if not title.startswith("[사설]"):
            title = "[사설] " + title
        date = None
        parent = a.find_parent(["li", "div", "article", "section", "tr"])
        if parent:
            pt = parent.get_text() or ""
            for dm in (
                re.search(r"(\d{4})\.(\d{2})\.(\d{2})", pt),
                re.search(r"(\d{4})-(\d{2})-(\d{2})", pt),
                re.search(r"(\d{4})(\d{2})(\d{2})", pt),
            ):
                if dm:
                    g = dm.groups()
                    if len(g) == 3:
                        date = f"{g[0]}-{g[1]}-{g[2]}"
                    elif len(g) == 1 and len(g[0]) >= 8:
                        s = g[0][:8]
                        date = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                    else:
                        date = None
                    if date:
                        break
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


class KmibScraper(BaseScraper):
    source_name = "국민일보"
    list_url = LIST_URL
    page_param = "page"
    max_pages = 12
    max_items = 200

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
                    results.extend(_parse_kmib_html(r.text, self.source_name))
                except Exception:
                    if page == 1:
                        return results
                    break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)][: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        all_ = await self.fetch_editorials()
        return [e for e in all_ if e.published_date == target_date]
