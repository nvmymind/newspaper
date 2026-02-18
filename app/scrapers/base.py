"""사설 스크래퍼 베이스 클래스."""
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from email.utils import parsedate_to_datetime
from typing import List

from app.models import Editorial

# 브라우저처럼 보이게 해서 목록 HTML을 받기 위한 공통 헤더
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# RSS 피드 요청용 헤더 (XML 수신 유도, 일부 사이트에서 HTML 대신 피드 반환)
RSS_HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml, */*;q=0.8",
}


class BaseScraper(ABC):
    source_name: str = ""
    list_url: str = ""
    # 페이지 파라미터 이름 (None이면 다중 페이지 미사용). 예: "page", "p"
    page_param: str | None = "page"
    max_pages: int = 3  # 수집할 최대 페이지 수 (날짜 범위 넓히기)
    max_items: int = 80  # 최대 기사 수

    def page_url(self, page: int) -> str:
        """페이지 번호(1-based)에 해당하는 목록 URL."""
        if page <= 1 or not self.page_param:
            return self.list_url
        sep = "&" if "?" in self.list_url else "?"
        return f"{self.list_url}{sep}{self.page_param}={page}"

    @abstractmethod
    async def fetch_editorials(self) -> List[Editorial]:
        """해당 신문사 사설 목록을 가져옵니다. published_date는 YYYY-MM-DD."""
        pass

    async def fetch_editorials_for_date(self, date: str) -> List[Editorial]:
        """해당 날짜(YYYY-MM-DD)의 사설만 수집. 기본은 전체 수집 후 날짜 필터."""
        all_ = await self.fetch_editorials()
        return [e for e in all_ if e.published_date == date]


def parse_rss_to_editorials(xml_text: str, source_name: str) -> List[Editorial]:
    """RSS/Atom XML 문자열을 파싱해 Editorial 리스트로 반환.
    RSS 2.0 (channel/item) 및 Atom (feed/entry) 기본 지원.
    """
    results: List[Editorial] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results

    # RSS 2.0: rss/channel/item (네임스페이스 있을 수 있음)
    channel = root.find("channel")
    if channel is None:
        for child in root:
            if child.tag == "channel" or (isinstance(child.tag, str) and child.tag.endswith("}channel")):
                channel = child
                break
    if channel is not None:
        for item in channel:
            if item.tag != "item" and not (isinstance(item.tag, str) and item.tag.endswith("}item")):
                continue
            title_el = item.find("title") or _rss_find_child(item, "title")
            link_el = item.find("link") or _rss_find_child(item, "link")
            pub_el = item.find("pubDate") or _rss_find_child(item, "pubDate")
            desc_el = item.find("description") or _rss_find_child(item, "description")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            date_str = _rss_date_to_yyyy_mm_dd(pub_el.text if pub_el is not None else "")
            summary = (desc_el.text or "").strip() if desc_el is not None else None
            if not summary:
                summary = None
            results.append(
                Editorial(
                    source=source_name,
                    title=title,
                    url=link,
                    summary=summary,
                    content=None,
                    published_date=date_str,
                )
            )
        return results

    # Atom: feed/entry
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for tag in ("entry", "{http://www.w3.org/2005/Atom}entry"):
        entries = root.findall(f".//{tag}")
        for entry in entries:
            title_el = entry.find("title") or entry.find("{http://www.w3.org/2005/Atom}title")
            link_el = entry.find("link") or entry.find("{http://www.w3.org/2005/Atom}link")
            updated_el = entry.find("updated") or entry.find("{http://www.w3.org/2005/Atom}updated")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = ""
            if link_el is not None:
                link = (link_el.get("href") or link_el.text or "").strip()
            if not title or not link:
                continue
            date_str = _rss_date_to_yyyy_mm_dd(updated_el.text if updated_el is not None else "")
            results.append(
                Editorial(
                    source=source_name,
                    title=title,
                    url=link,
                    summary=None,
                    content=None,
                    published_date=date_str,
                )
            )
        if results:
            return results

    return results


def _rss_local_name(tag: str) -> str:
    """XML 태그에서 로컬 이름 반환 (네임스페이스 제거)."""
    if isinstance(tag, str) and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _rss_find_child(parent, local_name: str):
    """자식 중 로컬 이름이 local_name인 첫 요소 반환."""
    for c in parent:
        if _rss_local_name(c.tag) == local_name:
            return c
    return None


def _rss_date_to_yyyy_mm_dd(pub_date: str) -> str:
    """RSS pubDate 또는 ISO 날짜를 YYYY-MM-DD로 변환."""
    pub_date = (pub_date or "").strip()
    if not pub_date:
        from datetime import date
        return date.today().isoformat()
    # ISO 8601
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", pub_date)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        dt = parsedate_to_datetime(pub_date)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        from datetime import date
        return date.today().isoformat()
