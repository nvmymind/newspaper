"""FastAPI 앱: 사설 수집·조회 API 및 웹 페이지."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

import aiosqlite

from app.database import get_db, init_db, DB_PATH
from app.scrapers import SCRAPERS

BASE_DIR = Path(__file__).resolve().parent.parent

# 수집 시 신문사당 최대 대기(초). 12월 등 과거 날짜까지 페이지를 많이 돌리므로 여유 있게.
FETCH_SCRAPER_TIMEOUT = 90


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await init_db(db)
    names = [s.source_name for s in (cls() for cls in SCRAPERS)]
    print(f"[신문 사설] 스크래퍼 {len(SCRAPERS)}개 로드: {', '.join(names)}")
    yield


app = FastAPI(title="신문 사설 모음", lifespan=lifespan)


# 정적 파일 및 템플릿 (프로젝트 루트 기준)
static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/health")
async def health():
    """Railway 등에서 서비스 생존 확인용. DB/템플릿 없이 즉시 200 반환."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _scraper_source_names():
    """현재 수집 대상 신문사 이름 목록 (목록/날짜 API에서 이 소스만 노출)."""
    return [cls().source_name for cls in SCRAPERS]


@app.get("/api/editorials")
async def list_editorials(
    date: str | None = Query(None, description="YYYY-MM-DD (없으면 오늘)"),
    source: str | None = Query(None, description="신문사 이름 필터"),
):
    """선택한 날짜의 사설을 실시간으로 스크랩해 반환. 3개 신문 병렬 수집으로 안정화."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    allowed = _scraper_source_names()
    if source and source not in allowed:
        return {"total": 0, "date": date, "items": [], "by_source": {}}

    # 필터 시: 해당 스크래퍼만, 전체: 3개 병렬 실행
    if source:
        to_run = [cls for cls in SCRAPERS if cls().source_name == source]
    else:
        to_run = list(SCRAPERS)

    async def run_one(ScraperCls):
        scraper = ScraperCls()
        try:
            editorials = await asyncio.wait_for(
                scraper.fetch_editorials_for_date(date), timeout=FETCH_SCRAPER_TIMEOUT
            )
            return scraper.source_name, editorials, {"count": len(editorials)}
        except asyncio.TimeoutError:
            return scraper.source_name, [], {"count": 0, "error": f"시간 초과({FETCH_SCRAPER_TIMEOUT}초)"}
        except Exception as e:
            return scraper.source_name, [], {"count": 0, "error": str(e)[:200]}

    results = await asyncio.gather(*[run_one(cls) for cls in to_run], return_exceptions=False)
    items = []
    by_source = {}
    for name, editorials, meta in results:
        by_source[name] = meta
        for e in editorials:
            items.append({
                "source": e.source,
                "title": e.title,
                "url": e.url,
                "summary": (e.summary or "")[:300],
                "published_date": e.published_date,
            })
    items.sort(key=lambda x: (x["source"], x["title"]))
    return {"total": len(items), "date": date, "items": items, "by_source": by_source}


@app.get("/api/dates")
async def list_dates(
    days: int = Query(90, ge=7, le=365, description="오늘 기준 최근 N일"),
):
    """선택 가능한 날짜 목록(오늘 기준 최근 N일). DB 미사용."""
    today = datetime.now().date()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    return {"dates": dates}


@app.get("/api/sources")
async def list_sources():
    """수집 대상 신문사 목록 (현재: 조선일보, 중앙일보)."""
    return {"sources": _scraper_source_names()}


@app.get("/api/scrapers")
async def list_scrapers():
    """현재 수집 대상 스크래퍼 목록."""
    return {"count": len(SCRAPERS), "sources": _scraper_source_names()}


