"""FastAPI 앱: 사설 수집·조회 API 및 웹 페이지."""
import asyncio
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Query
from fastapi.responses import RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

import aiosqlite

from app.database import get_db, init_db, DB_PATH
from app.scrapers import SCRAPERS

# 수집 시 신문사당 최대 대기(초). 12월 등 과거 날짜까지 페이지를 많이 돌리므로 여유 있게.
FETCH_SCRAPER_TIMEOUT = 90


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await init_db(db)
    names = [s.source_name for s in (cls() for cls in SCRAPERS)]
    print(f"[신문 사설] 스크래퍼 {len(SCRAPERS)}개 로드: {', '.join(names)}")
    if os.environ.get("GOOGLE_CLIENT_ID"):
        print("[유튜브] Google 로그인: 설정됨")
    else:
        print("[유튜브] Google 로그인: .env에 GOOGLE_CLIENT_ID가 없습니다. 유튜브 구독 영상 로그인이 동작하지 않습니다.")
    yield


app = FastAPI(title="신문 사설 모음", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """어떤 요청에서든 예외가 나면 서버가 죽지 않고 응답을 돌려줌."""
    print(f"[오류] {request.url.path}: {exc!r}")
    if request.url.path.startswith("/api/"):
        return PlainTextResponse(f"오류: {str(exc)[:200]}", status_code=500)
    return PlainTextResponse("일시적인 오류가 발생했습니다. 새로고침해 주세요.", status_code=500)


# 세션 (유튜브 구독 영상용 Google 로그인)
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-use-env")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=14 * 24 * 3600)

# 정적 파일 및 템플릿 (프로젝트 루트 기준)
static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/health")
async def health():
    """Railway 등에서 서비스 생존 확인용. DB/템플릿 없이 즉시 200 반환."""
    return {"status": "ok"}


@app.get("/api/site-verification-status")
async def site_verification_status():
    """Search Console용 meta 태그가 head에 넣어질 값이 있는지 확인. set: true면 정상."""
    content = _google_site_verification_content()
    return {"set": bool(content)}


def _google_site_verification_content() -> str:
    """GOOGLE_SITE_VERIFICATION에서 content 값만 추출. meta 태그 전체를 넣어도 동작."""
    raw = (os.environ.get("GOOGLE_SITE_VERIFICATION") or "").strip()
    if not raw:
        return ""
    # content="...값..." 또는 content='...값...' 형태에서 값만 추출
    for prefix, q in [('content="', '"'), ("content='", "'")]:
        if prefix in raw:
            start = raw.find(prefix) + len(prefix)
            end = raw.find(q, start)
            if end != -1:
                return raw[start:end].strip()
    # 이미 content 값만 있는 경우(영문·숫자 조합) 그대로 사용
    return raw


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        google_site_verification = _google_site_verification_content()
        # 템플릿 변수와 무관하게, 값이 있으면 렌더된 HTML에 meta 태그 직접 삽입 (Search Console 인식 보장)
        template = templates.env.get_template("index.html")
        body = template.render(
            {"request": request, "google_site_verification": google_site_verification}
        )
        if google_site_verification:
            meta = (
                f'<meta name="google-site-verification" content="{google_site_verification}" />\n  '
            )
            # </head> 바로 앞에 삽입 (viewport 문자열 차이에 영향받지 않음)
            if "</head>" in body:
                body = body.replace("</head>", meta + "</head>", 1)
            else:
                # </head>가 없으면 <head> 다음에라도 넣기 (대소문자·공백 차이 대비)
                body = re.sub(r"<head[^>]*>", "\\g<0>\\n  " + meta, body, count=1)
        return HTMLResponse(body)
    except Exception as e:
        print(f"[오류] 메인 페이지: {e!r}")
        return PlainTextResponse("메인 페이지를 불러오지 못했습니다. 새로고침해 주세요.", status_code=500)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """개인정보처리방침 (Google OAuth 동의 화면·검증용 URL)."""
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """서비스 약관 (Google OAuth 동의 화면·검증용 URL)."""
    return templates.TemplateResponse("terms.html", {"request": request})


def _scraper_source_names():
    """현재 수집 대상 신문사 이름 목록 (목록/날짜 API에서 이 소스만 노출)."""
    return [cls().source_name for cls in SCRAPERS]


@app.get("/api/editorials")
async def list_editorials(
    date: str | None = Query(None, description="YYYY-MM-DD (없으면 오늘)"),
    source: str | None = Query(None, description="신문사 이름 필터"),
):
    """선택한 날짜의 사설을 실시간으로 스크랩해 반환. 3개 신문 병렬 수집으로 안정화."""
    try:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        allowed = _scraper_source_names()
        if source and source not in allowed:
            return {"total": 0, "date": date, "items": [], "by_source": {}}

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
    except Exception as e:
        fallback_date = datetime.now().strftime("%Y-%m-%d")
        return {"total": 0, "date": fallback_date, "items": [], "by_source": {"오류": {"count": 0, "error": str(e)[:200]}}}


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


# ----- 유튜브 구독 영상 (기존 사설 기능과 무관) -----
from app.youtube_service import get_google_oauth_url, exchange_code_for_tokens, fetch_subscription_feed


def _google_configured() -> bool:
    """GOOGLE_CLIENT_ID가 비어 있지 않으면 True (공백·빈 문자열 제외)."""
    v = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    return bool(v)


def _base_url_for_oauth(request: Request, _debug: dict | None = None) -> str:
    """OAuth 리디렉션 URI용 기준 URL. 프로덕션(실제 도메인)이면 항상 https 사용."""
    base = (os.environ.get("OAUTH_BASE_URL") or "").strip()
    if base:
        if _debug is not None:
            _debug["base_출처"] = "OAUTH_BASE_URL"
        return base.rstrip("/")
    # 프록시가 넘긴 원본 호스트 우선, 없으면 요청 URL의 host
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        try:
            host = (getattr(request.url, "hostname", None) or "").strip()
        except Exception:
            pass
    if _debug is not None:
        _debug["감지된_host"] = host or "(없음)"
    if not host:
        if _debug is not None:
            _debug["base_출처"] = "request.base_url"
        return str(request.base_url).rstrip("/")
    # localhost/127.0.0.1 이 아니면 프로덕션으로 보고 https 고정
    if host.lower() not in ("localhost", "127.0.0.1") and "127.0.0.1" not in host:
        if _debug is not None:
            _debug["base_출처"] = "프로덕션(https 고정)"
        return f"https://{host}"
    proto = request.headers.get("x-forwarded-proto", "").strip().lower()
    if proto == "https":
        if _debug is not None:
            _debug["base_출처"] = "x-forwarded-proto"
        return f"https://{host}"
    if _debug is not None:
        _debug["base_출처"] = "request.base_url"
    return str(request.base_url).rstrip("/")


@app.get("/auth/google")
async def auth_google(request: Request):
    """Google 로그인 페이지로 리다이렉트."""
    try:
        if not _google_configured():
            print("[유튜브] /auth/google: GOOGLE_CLIENT_ID가 비어 있음 → /youtube?error=config")
            return RedirectResponse(url="/youtube?error=config", status_code=302)
        base = _base_url_for_oauth(request)
        redirect_uri = f"{base}/auth/google/callback"
        url = get_google_oauth_url(redirect_uri=redirect_uri)
        return RedirectResponse(url=url)
    except Exception as e:
        print(f"[유튜브] /auth/google 예외: {e!r}")
        return RedirectResponse(url="/youtube?error=config", status_code=302)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, code: str | None = None):
    """Google OAuth 콜백: 토큰 저장 후 /youtube로 이동."""
    youtube_url = "/youtube"
    try:
        if not code:
            return RedirectResponse(url=youtube_url, status_code=302)
        base = _base_url_for_oauth(request)
        redirect_uri = f"{base}/auth/google/callback"
        tokens = await exchange_code_for_tokens(code, redirect_uri)
        if not tokens:
            return RedirectResponse(url=f"{youtube_url}?error=login_failed", status_code=302)
        request.session["google_access_token"] = tokens.get("access_token")
        request.session["google_refresh_token"] = tokens.get("refresh_token")
        return RedirectResponse(url=youtube_url, status_code=302)
    except Exception:
        return RedirectResponse(url=f"{youtube_url}?error=login_failed", status_code=302)


@app.get("/api/youtube/config")
async def api_youtube_config():
    """Google 로그인 설정 여부 (유튜브 페이지에서 로그인 버튼 노출 판단용)."""
    return {"configured": _google_configured()}


@app.get("/api/youtube/debug")
async def api_youtube_debug(request: Request):
    """구글 로그인 원인 확인용. 브라우저에서 같은 포트로 열어보세요."""
    debug_info: dict = {}
    base = _base_url_for_oauth(request, _debug=debug_info)
    redirect_uri = f"{base}/auth/google/callback"
    return {
        "configured": _google_configured(),
        "redirect_uri_등록할값": redirect_uri,
        **debug_info,
        "설명": "configured가 true인데 로그인 안 되면, 위 redirect_uri_등록할값을 Google 콘솔 승인된 리디렉션 URI에 정확히 넣었는지 확인하세요.",
    }


@app.get("/youtube", response_class=HTMLResponse)
async def youtube_page(request: Request):
    """유튜브 구독 영상 페이지 (새 창)."""
    return templates.TemplateResponse("youtube.html", {"request": request})


@app.get("/api/youtube/feed")
async def api_youtube_feed(request: Request):
    """구독 채널·최신 영상 피드 (로그인 필요)."""
    access = request.session.get("google_access_token")
    refresh = request.session.get("google_refresh_token")
    if not access and not refresh:
        return {"logged_in": False, "channels": [], "videos": []}
    try:
        channels, videos, new_token = await fetch_subscription_feed(access, refresh)
        if new_token:
            request.session["google_access_token"] = new_token
        return {"logged_in": True, "channels": channels, "videos": videos}
    except Exception as e:
        return {"logged_in": True, "channels": [], "videos": [], "error": str(e)[:200]}


@app.get("/api/youtube/logout")
async def api_youtube_logout(request: Request):
    """Google 로그아웃 후 /youtube로 리다이렉트."""
    request.session.clear()
    return RedirectResponse(url=request.url_for("youtube_page"), status_code=302)


