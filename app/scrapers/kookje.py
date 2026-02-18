"""국제신문 사설 스크래퍼."""
import re
from typing import List

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

# 국제신문 사설 목록 (code=1710)
LIST_URL = "https://www.kookje.co.kr/news2011/asp/list.asp?code=1710"
BASE_URL = "https://www.kookje.co.kr"


def _parse_kookje_html(html: str, source_name: str) -> List[Editorial]:
    results: List[Editorial] = []
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href*='newsbody.asp']"):
        href = (a.get("href") or "").strip()
        if not href or "javascript" in href:
            continue
        # HTML 내 &amp; 정규화
        href = href.replace("&amp;", "&")
        if "key=" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + "/news2011/asp/" + href.lstrip("/")
        href = href.split("#")[0]
        # key=YYYYMMDD 또는 key=YYYYMMDD.숫자 형식
        m = re.search(r"key=(\d{4})(\d{2})(\d{2})(?:\.\d+)?", href)
        if not m:
            continue
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        title_el = a.select_one("h2, h3, h4, .tit, .title, [class*='title']") or a
        title = (title_el.get_text(strip=True) or "").strip()
        # 요약이 붙은 경우 첫 줄만 사용(줄바꿈·대괄호 구간으로 제목만 추출)
        if "\n" in title:
            title = title.split("\n")[0].strip()
        if len(title) > 300:
            title = title[:300].rstrip()
        if not title or len(title) < 3:
            continue
        # 사설 목록 페이지(code=1710) 링크는 kid=1710 → 사설로 간주
        is_editorial_page = "kid=1710" in href or "code=1710" in href
        if not is_editorial_page:
            if "[사설]" not in title:
                parent = a.find_parent(["li", "div", "article", "p", "td"])
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


class KookjeScraper(BaseScraper):
    source_name = "국제신문"
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
                    # 국제신문은 EUC-KR/CP949 인코딩 사용 → UTF-8로 디코딩 후 파싱
                    try:
                        html = r.content.decode("euc-kr")
                    except (UnicodeDecodeError, LookupError):
                        html = r.content.decode("cp949", errors="replace")
                    results.extend(_parse_kookje_html(html, self.source_name))
                except Exception:
                    if page == 1:
                        return results
                    break
        seen = set()
        return [e for e in results if e.url not in seen and not seen.add(e.url)][: self.max_items]

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        all_ = await self.fetch_editorials()
        return [e for e in all_ if e.published_date == target_date]
