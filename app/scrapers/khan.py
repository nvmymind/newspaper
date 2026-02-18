"""경향신문 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper

LIST_URL = "https://www.khan.co.kr/opinion/editorial/articles"


class KhanScraper(BaseScraper):
    source_name = "경향신문"
    list_url = LIST_URL
    page_param = "page"
    max_pages = 12
    max_items = 200

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
                for a in soup.select("a[href*='/article/']"):
                    href = a.get("href") or ""
                    if not href.startswith("http"):
                        href = "https://www.khan.co.kr" + href
                    href_clean = href.split("?")[0]
                    if "?page=" in href or not re.search(r"/article/\d{10,}", href_clean):
                        continue
                    title_el = a.select_one("h2, h3, h4, .title, [class*='headline'], [class*='title']") or a
                    title = (title_el.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        parent = a.find_parent(["article", "li", "div"])
                        if parent:
                            h = parent.select_one("h2, h3, h4, [class*='title']")
                            if h:
                                title = (h.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        continue
                    m = re.search(r"/article/(\d{4})(\d{2})(\d{2})\d+", href_clean)
                    if not m:
                        continue
                    date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    results.append(
                        Editorial(
                            source=self.source_name,
                            title=title,
                            url=href_clean,
                            summary=None,
                            content=None,
                            published_date=date,
                        )
                    )
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]
