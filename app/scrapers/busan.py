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


def _ancestor_contains(a, needle: str, max_depth: int = 15) -> bool:
    """링크의 조상 중 하나에 needle 문자열이 포함돼 있는지 확인."""
    p = a.parent
    for _ in range(max_depth):
        if p is None:
            return False
        if needle in (p.get_text() or ""):
            return True
        p = p.parent
    return False


def _parse_busan_html(html: str, source_name: str) -> List[Editorial]:
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    # view.php?code= 형태 링크 (부산일보 기사 공통)
    for a in soup.select("a[href*='code=']"):
        href = (a.get("href") or "").strip()
        if not href or "javascript" in href or "view.php" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + href if href.startswith("/") else BASE_URL + "/" + href
        href = href.split("#")[0]
        m = re.search(r"code=(\d{8})", href)
        if not m:
            continue
        date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
        title_el = a.select_one("h2, h3, h4, .tit, .title, [class*='title'], [class*='headline']") or a
        title = (title_el.get_text(strip=True) or "").strip()
        if len(title) > 200:
            title = title[:197] + "..."
        if not title or len(title) < 2:
            continue
        # 사설만: 제목 또는 위쪽 조상에 '사설' 포함 (섹션 제목·블록 텍스트 포함)
        if "사설" not in title and not _ancestor_contains(a, "사설"):
            continue
        if not title.startswith("[사설]") and "[사설]" not in title:
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
