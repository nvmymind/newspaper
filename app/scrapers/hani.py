"""한겨레 사설 스크래퍼 (사설 속으로 등)."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper

# 한겨레 사설 목록 (list.html 아님). 페이지: ?page=2
LIST_URL = "https://www.hani.co.kr/arti/opinion/editorial"


class HaniScraper(BaseScraper):
    source_name = "한겨레"
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
                for a in soup.select("a[href*='/arti/opinion/editorial/']"):
                    href = a.get("href") or ""
                    if not href.startswith("http"):
                        href = "https://www.hani.co.kr" + href
                    if ".html" not in href:
                        continue
                    title_el = a.select_one(".article-title, .tit, h2, h3, .title") or a
                    title = (title_el.get_text(strip=True) or "").strip()
                    if not title or len(title) < 2:
                        continue
                    date = None
                    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", href)
                    if m:
                        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    else:
                        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", href)
                        if m:
                            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    if not date:
                        parent = a.find_parent(["li", "div", "article", "section"])
                        if parent:
                            pt = parent.get_text()
                            dm = re.search(r"(\d{4})-(\d{2})-(\d{2})", pt)
                            if not dm:
                                dm = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", pt)
                            if dm:
                                date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                    if not date:
                        continue
                    # 요약: 목록 항목 본문 일부(칼럼형 미리보기)
                    summary = None
                    parent = a.find_parent(["li", "div", "article", "section"])
                    if parent:
                        desc = parent.select_one("p, .article-summary, [class*='desc'], [class*='lead']")
                        if desc and desc != title_el:
                            summary = (desc.get_text(strip=True) or "").replace(title, "", 1).strip()[:220]
                        if not summary and parent:
                            full = parent.get_text(separator=" ", strip=True)
                            if len(full) > len(title) + 20:
                                summary = full[len(title):].strip()[:220]
                    results.append(
                        Editorial(
                            source=self.source_name,
                            title=title,
                            url=href.split("?")[0],
                            summary=summary,
                            content=None,
                            published_date=date,
                        )
                    )
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]
