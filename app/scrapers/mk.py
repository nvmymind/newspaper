"""매일경제 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

LIST_URL = "https://www.mk.co.kr/opinion/editorial/"


class MkScraper(BaseScraper):
    source_name = "매일경제"
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
                try:
                    r = await client.get(self.page_url(page))
                    r.raise_for_status()
                except Exception:
                    if page == 1:
                        return results
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a[href*='/news/editorial/']"):
                    href = a.get("href") or ""
                    if not href.startswith("http"):
                        href = "https://www.mk.co.kr" + href
                    href = href.split("?")[0]
                    if not re.search(r"/news/editorial/\d+$", href):
                        continue
                    parent = a.find_parent(["li", "div", "article", "section"])
                    # 날짜: 부모·형제·링크 본문에서 2026.02.10 또는 02.10 2026 등 추출
                    date = None
                    for node in ([parent] if parent else []) + [a]:
                        if not node:
                            continue
                        pt = node.get_text() or ""
                        dm = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", pt)
                        if not dm:
                            dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", pt)
                        if not dm:
                            dm = re.search(r"(\d{2})\.(\d{2})\s+(\d{4})", pt)
                            if dm:
                                date = f"{dm.group(3)}-{dm.group(1)}-{dm.group(2)}"
                                break
                        if dm and not date:
                            date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                            break
                    if not date:
                        continue
                    title_el = a.select_one("h2, h3, h4, h5, .tit, .title, [class*='title']") or a
                    title = (title_el.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        if parent:
                            h = parent.select_one("h2, h3, h4, h5, .tit, [class*='title']")
                            if h:
                                title = (h.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        continue
                    if "[사설]" not in title and parent and "[사설]" in (parent.get_text() or ""):
                        title = title + " [사설]" if "[사설]" not in title else title
                    summary = None
                    if parent:
                        desc = parent.select_one("p, [class*='desc'], [class*='summary']")
                        if desc:
                            summary = (desc.get_text(strip=True) or "")[:200]
                    results.append(
                        Editorial(
                            source=self.source_name,
                            title=title,
                            url=href,
                            summary=summary,
                            content=None,
                            published_date=date,
                        )
                    )
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]
