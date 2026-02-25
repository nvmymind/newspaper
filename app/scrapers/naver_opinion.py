"""네이버 오피니언 사설 수집.
   [방식 1] Playwright로 사설 탭 페이지를 열고 끝까지 스크롤해 로드된 전체 HTML에서
            mnews/article 링크를 모두 추출 → 네이버에 보이는 것과 동일한 목록·개수.
   [방식 2] Playwright 미사용 시: editorial 페이지(httpx) + list.naver 페이지네이션 보조,
            제목은 항상 채우도록 보정.
"""
import asyncio
import re
from typing import List, Set, Tuple

import httpx
from bs4 import BeautifulSoup

from app.models import Editorial
from app.scrapers.base import BaseScraper, BROWSER_HEADERS

NAVER_EDITORIAL_URL = "https://news.naver.com/opinion/editorial"
NAVER_LIST_URL = "https://news.naver.com/main/list.naver"
TIME_SUFFIX_RE = re.compile(r"\s*\d+(시간|분|일)전\s*$")
EDITORIAL_MARKERS = ("[사설]", "[논설실의 관점]")

# 네이버 뉴스 언론사 oid → 신문사명 (list.naver 수집 시 '기타' 방지용). officeList.naver 기준 보강.
NAVER_OID_NAMES = {
    "001": "연합뉴스", "002": "프레시안", "003": "뉴시스", "005": "국민일보",
    "006": "미디어오늘", "007": "일다", "008": "머니투데이", "009": "매일경제",
    "011": "서울경제", "014": "파이낸셜뉴스", "015": "한국경제", "016": "헤럴드경제",
    "018": "이데일리", "020": "동아일보", "021": "문화일보", "022": "세계일보",
    "023": "조선일보", "024": "매경이코노미", "025": "중앙일보", "028": "한겨레",
    "029": "디지털타임스", "030": "전자신문", "031": "아이뉴스24", "032": "경향신문",
    "033": "주간경향", "036": "한겨레21", "037": "주간동아", "044": "코리아헤럴드",
    "047": "오마이뉴스", "050": "한경비즈니스", "052": "YTN", "053": "주간조선",
    "055": "SBS", "056": "KBS", "057": "MBN", "079": "노컷뉴스", "081": "서울신문",
    "082": "부산일보", "087": "강원일보", "088": "매일신문", "092": "지디넷코리아",
    "094": "월간 산", "119": "데일리안", "123": "조세일보", "127": "기자협회보",
    "138": "디지털데일리", "145": "레이디경향", "214": "MBC", "215": "한국경제TV",
    "243": "이코노미스트", "262": "신동아", "277": "아시아경제", "293": "블로터",
    "296": "코메디닷컴", "308": "시사IN", "310": "여성신문", "346": "헬스조선",
    "366": "조선비즈", "374": "SBS Biz", "417": "동행미디어 시대", "421": "뉴스1",
    "422": "연합뉴스TV", "437": "JTBC", "448": "TV조선", "449": "채널A",
    "469": "한국일보", "584": "동아사이언스", "586": "시사저널", "607": "뉴스타파",
    "629": "더팩트", "640": "코리아중앙데일리", "648": "비즈워치", "654": "강원도민일보",
    "655": "CJB청주방송", "656": "대전일보", "657": "대구MBC", "658": "국제신문",
    "659": "전주MBC", "660": "kbc광주방송", "661": "JIBS", "662": "농민신문",
    "665": "더스쿠프", "666": "경기일보",
}


def _date_to_naver_param(date: str) -> str:
    if not date or len(date) < 10:
        return date.replace("-", "")
    return date[:4] + date[5:7] + date[8:10]


def _parse_link_text(text: str) -> Tuple[str, str]:
    """'신문사명 제목 N시간전' → (신문사명, 제목). 제목이 비면 링크 텍스트 일부를 제목으로."""
    text = TIME_SUFFIX_RE.sub("", (text or "").strip()).strip()
    if not text:
        return "", ""
    parts = text.split(None, 1)
    if len(parts) == 1:
        return parts[0], parts[0][:120] if len(parts[0]) > 120 else parts[0]
    title = parts[1].strip()
    if not title:
        title = parts[0][:120]
    return parts[0], title


def _ensure_title(raw: str, normalized: str, max_len: int = 200) -> str:
    """제목이 비지 않도록 보정."""
    s = (normalized or "").strip()
    if s:
        return s[:max_len] if len(s) > max_len else s
    s = TIME_SUFFIX_RE.sub("", (raw or "").strip()).strip()
    for m in EDITORIAL_MARKERS:
        s = s.replace(m, "").strip()
    s = s.strip()
    if s:
        return s[:max_len] if len(s) > max_len else s
    return "제목 없음"


def _oid_from_url(href: str) -> str:
    m = re.search(r"/mnews/article/(\d+)/", href)
    return m.group(1) if m else ""


def _parse_editorial_page_html(html: str, date: str) -> List[Editorial]:
    """사설 탭 HTML(전체 로드된 상태)에서 mnews/article 링크만 추출. 형식: 신문사명 제목 N시간전."""
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()
    results: List[Editorial] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if "n.news.naver.com/mnews/article/" not in href:
            continue
        if not href.startswith("http"):
            href = "https://n.news.naver.com" + href.split("n.news.naver.com")[-1]
        if "?" not in href:
            href = href + "?sid=110"
        if href in seen:
            continue
        seen.add(href)
        text = a.get_text(strip=True)
        source, title = _parse_link_text(text)
        title = _ensure_title(text, title)
        if not source:
            source = "알 수 없음"
        results.append(
            Editorial(
                source=source,
                title=title,
                url=href,
                summary=None,
                content=None,
                published_date=date,
            )
        )
    return results


def _parse_list_naver_page(html: str, date: str, seen_urls: Set[str]) -> List[Editorial]:
    """list.naver 한 페이지에서 [사설]/[논설실의 관점] 링크만. 제목 항상 보정."""
    soup = BeautifulSoup(html, "html.parser")
    results: List[Editorial] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if "mnews/article/" not in href:
            continue
        if not href.startswith("http"):
            href = "https://n.news.naver.com" + href.split("n.news.naver.com")[-1]
        if "?" not in href:
            href = href + "?sid=110"
        if href in seen_urls:
            continue
        link_text = a.get_text(strip=True)
        if not any(m in link_text for m in EDITORIAL_MARKERS):
            parent = a.find_parent(["li", "dd", "dt"])
            if not parent or not any(m in parent.get_text(" ", strip=True) for m in EDITORIAL_MARKERS):
                continue
        seen_urls.add(href)
        raw = link_text
        title = raw
        for m in EDITORIAL_MARKERS:
            title = title.replace(m, "").strip()
        title = re.sub(r"\s*\[사설\]\s*$", "", title).strip()
        title = _ensure_title(raw, title)
        oid = _oid_from_url(href)
        source = NAVER_OID_NAMES.get(oid, "")
        if not source:
            parent = a.find_parent(["li", "dd", "dt"])
            if parent:
                full = parent.get_text(" ", strip=True)
                for name in NAVER_OID_NAMES.values():
                    if name in full and (full.endswith(name) or f" {name} " in full or full.strip().endswith(f" {name}")):
                        source = name
                        break
        if not source:
            source = "기타"
        results.append(
            Editorial(
                source=source,
                title=title,
                url=href,
                summary=None,
                content=None,
                published_date=date,
            )
        )
    return results


async def _fetch_full_editorial_with_playwright(url: str) -> str | None:
    """Playwright로 사설 탭 열고, 기사 링크 수가 더 이상 늘지 않을 때까지 스크롤 후 HTML 반환."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(2.5)
                last_count = 0
                stable_rounds = 0
                max_stable = 4
                for _ in range(55):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.2)
                    try:
                        more = await page.query_selector("text=더보기")
                        if more:
                            await more.click()
                            await asyncio.sleep(1.5)
                    except Exception:
                        pass
                    html = await page.content()
                    count = html.count("mnews/article/")
                    if count > 0 and count == last_count:
                        stable_rounds += 1
                        if stable_rounds >= max_stable:
                            break
                    else:
                        stable_rounds = 0
                    last_count = count
                return await page.content()
            finally:
                await browser.close()
    except Exception as e:
        err = str(e).lower()
        if "executable" in err or "browser" in err or "chromium" in err:
            pass
        return None


class NaverOpinionScraper(BaseScraper):
    """네이버 오피니언 사설 — Playwright 우선(전체 로드), 미사용 시 editorial+list 보조."""

    source_name = "네이버 오피니언"
    list_url = NAVER_EDITORIAL_URL
    page_param = None
    max_pages = 1
    max_items = 250
    LIST_NAVER_MAX_PAGES = 30

    async def fetch_editorials(self) -> List[Editorial]:
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        return await self.fetch_editorials_for_date(today)

    async def fetch_editorials_for_date(self, date: str) -> List[Editorial]:
        param = _date_to_naver_param(date)
        url_editorial = f"{NAVER_EDITORIAL_URL}?date={param}" if param else NAVER_EDITORIAL_URL
        items: List[Editorial] = []
        seen_urls: Set[str] = set()

        # 1) Playwright로 사설 탭 전체 로드 시도 (실패/타임아웃 시 바로 httpx로 넘어감)
        html = None
        try:
            html = await asyncio.wait_for(
                _fetch_full_editorial_with_playwright(url_editorial),
                timeout=18.0,
            )
        except (asyncio.TimeoutError, Exception):
            pass
        if html:
            items = _parse_editorial_page_html(html, date)
            seen_urls = {e.url for e in items}

        # 2) 수집이 30개 미만이면 editorial(httpx) + list.naver 보조로 보강 (기존 항목 유지·병합)
        if len(items) < 30:
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    headers={**BROWSER_HEADERS, "Referer": "https://news.naver.com/"},
                    timeout=22.0,
                ) as client:
                    r = await client.get(url_editorial)
                    r.raise_for_status()
                    extra_from_editorial = _parse_editorial_page_html(r.text, date)
                    for e in extra_from_editorial:
                        if e.url not in seen_urls:
                            seen_urls.add(e.url)
                            items.append(e)
                    # list.naver: listType=paper(신문게재) → 없으면 listType=title 시도
                    for list_type in ("paper", "title"):
                        added_any = False
                        for page in range(1, self.LIST_NAVER_MAX_PAGES + 1):
                            list_url = f"{NAVER_LIST_URL}?mode=LSD&mid=sec&sid1=110&listType={list_type}&date={param}&page={page}"
                            r2 = await client.get(list_url)
                            r2.raise_for_status()
                            extra = _parse_list_naver_page(r2.text, date, seen_urls)
                            for e in extra:
                                items.append(e)
                                seen_urls.add(e.url)
                                added_any = True
                            if not extra:
                                break
                        if list_type == "paper" and added_any:
                            break
            except Exception as e:
                if not items:
                    raise RuntimeError(f"네이버 오피니언 사설 요청 실패: {e}") from e

        seen = set()
        unique: List[Editorial] = []
        for e in items:
            if e.url not in seen:
                seen.add(e.url)
                title = (e.title or "").strip() or "제목 없음"
                unique.append(
                    Editorial(source=e.source, title=title, url=e.url, summary=e.summary, content=e.content, published_date=e.published_date)
                )
        return unique[: self.max_items]
