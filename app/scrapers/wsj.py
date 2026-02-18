"""Wall Street Journal Opinion 스크래퍼. RSS 피드 사용."""
from datetime import datetime, timedelta
from typing import List

import httpx

from app.models import Editorial
from app.scrapers.base import BaseScraper, parse_rss_to_editorials, RSS_HEADERS

# WSJ 오피니언 공식 RSS (웹 페이지는 페이월/접근 제한)
RSS_URL = "https://feeds.content.dowjones.io/public/rss/RSSOpinion"


class WsjScraper(BaseScraper):
    source_name = "Wall Street Journal"
    list_url = RSS_URL
    page_param = None
    max_pages = 1
    max_items = 80

    async def fetch_editorials(self) -> List[Editorial]:
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                headers=RSS_HEADERS,
                timeout=25.0,
            ) as client:
                r = await client.get(RSS_URL)
                r.raise_for_status()
                items = parse_rss_to_editorials(r.text, self.source_name)
                return items[: self.max_items]
        except Exception:
            return []

    async def fetch_editorials_for_date(self, target_date: str) -> List[Editorial]:
        all_ = await self.fetch_editorials()
        try:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            prev = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            allowed = {target_date, prev}
        except ValueError:
            allowed = {target_date}
        return [e for e in all_ if e.published_date in allowed]
