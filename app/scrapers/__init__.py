"""신문사별 사설 스크래퍼. 네이버 오피니언 사설 코너에서 모든 신문사 사설을 한 번에 수집."""
from app.scrapers.base import BaseScraper
from app.scrapers.naver_opinion import NaverOpinionScraper

# 네이버 오피니언 사설 한 코너에서 모든 신문사 사설 수집 (날짜별 검색 지원)
SCRAPERS: list[type[BaseScraper]] = [
    NaverOpinionScraper,
]
