"""신문사별 사설 스크래퍼."""
from app.scrapers.base import BaseScraper
from app.scrapers.busan import BusanScraper
from app.scrapers.chosun import ChosunScraper
from app.scrapers.donga import DongaScraper
from app.scrapers.hani import HaniScraper
from app.scrapers.hankyung import HankyungScraper
from app.scrapers.joongang import JoongangScraper
from app.scrapers.khan import KhanScraper
from app.scrapers.kookje import KookjeScraper
from app.scrapers.mk import MkScraper
from app.scrapers.wsj import WsjScraper

SCRAPERS: list[type[BaseScraper]] = [
    ChosunScraper,
    JoongangScraper,
    DongaScraper,
    KhanScraper,           # 경향신문
    HaniScraper,           # 한겨레
    MkScraper,             # 매일경제
    HankyungScraper,       # 한국경제신문
    BusanScraper,          # 부산일보
    KookjeScraper,         # 국제신문
    WsjScraper,            # 월스트리트저널
]
