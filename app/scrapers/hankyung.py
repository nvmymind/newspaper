"""한국경제신문 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper

LIST_URL = "https://www.hankyung.com/opinion/0001"  # 사설


class HankyungScraper(BaseScraper):
    source_name = "한국경제신문"
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
                for block in soup.select("article, li, div[class*='news'], div[class*='list'], div[class*='item']"):
                    text = block.get_text()
                    if "[사설]" not in text:
                        continue
                    a = block.select_one("a[href*='/article/']")
                    if not a:
                        continue
                    href = a.get("href") or ""
                    if not href.startswith("http"):
                        href = "https://www.hankyung.com" + href
                    if not re.search(r"/article/\d+", href):
                        continue
                    title_el = block.select_one("h2, h3, h4, [class*='title'], [class*='headline']") or a
                    title = (title_el.get_text(strip=True) or "").strip()
                    if not title or not title.startswith("[사설]"):
                        continue
                    date = None
                    m = re.search(r"/article/(\d{4})(\d{2})(\d{2})", href)
                    if m:
                        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                    else:
                        dm = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
                        if dm:
                            date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                    if not date:
                        continue
                    results.append(
                        Editorial(
                            source=self.source_name,
                            title=title,
                            url=href.split("?")[0],
                            summary=None,
                            content=None,
                            published_date=date,
                        )
                    )
                # 방법 2: 블록에서 못 찾으면 a 링크 순회, 제목은 부모에서 [사설] 포함 텍스트
                if not results:
                    for a in soup.select("a[href*='/article/']"):
                        href = a.get("href") or ""
                        if not href.startswith("http"):
                            href = "https://www.hankyung.com" + href
                        if not re.search(r"/article/\d+", href):
                            continue
                        parent = a.find_parent(["li", "div", "article"])
                        if not parent or "[사설]" not in parent.get_text():
                            continue
                        title_el = parent.select_one("h2, h3, h4, [class*='title']") or a
                        title = (title_el.get_text(strip=True) or "").strip()
                        if not title.startswith("[사설]"):
                            continue
                        date = None
                        m = re.search(r"/article/(\d{4})(\d{2})(\d{2})", href)
                        if m:
                            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                        else:
                            dm = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", parent.get_text())
                            if dm:
                                date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                        if not date:
                            continue
                        results.append(
                            Editorial(
                                source=self.source_name,
                                title=title,
                                url=href.split("?")[0],
                                summary=None,
                                content=None,
                                published_date=date,
                            )
                        )
        seen = set()
        unique = [e for e in results if e.url not in seen and not seen.add(e.url)]
        return unique[: self.max_items]
