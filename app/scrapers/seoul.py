"""서울신문 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper

LIST_URL = "https://www.seoul.co.kr/newsList/editOpinion/editorial/"


class SeoulScraper(BaseScraper):
    source_name = "서울신문"
    list_url = LIST_URL

    async def fetch_editorials(self) -> List[Editorial]:
        results: List[Editorial] = []
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15.0,
        ) as client:
            for page in range(1, self.max_pages + 1):
                try:
                    r = await client.get(self.page_url(page))
                    r.raise_for_status()
                except Exception:
                    if page == 1:
                        return results
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a[href*='editorial/']"):
                    href = a.get("href") or ""
                    if not href.startswith("http"):
                        href = "https://www.seoul.co.kr" + href
                    href = href.split("?")[0]
                    # editorial/2026/02/12/20260212027003 형태만
                    m = re.search(r"/editorial/(\d{4})/(\d{2})/(\d{2})/\d+", href)
                    if not m:
                        continue
                    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    title_el = a.select_one("h2, h3, h4, .tit, .title, [class*='title']") or a
                    title = (title_el.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        parent = a.find_parent(["article", "li", "div", "section"])
                        if parent:
                            h = parent.select_one("h2, h3, h4, [class*='title']")
                            if h:
                                title = (h.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        continue
                    results.append(
                        Editorial(
                            source=self.source_name,
                            title=title,
                            url=href,
                            summary=None,
                            content=None,
                            published_date=date,
                        )
                    )
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]
