"""Google OAuth 및 YouTube Data API v3 연동 (구독 채널·최신 영상)."""
import os
from urllib.parse import urlencode

import httpx

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


def get_google_oauth_url(redirect_uri: str, state: str | None = None) -> str:
    """Google 로그인 페이지 URL 생성."""
    client_id = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict | None:
    """인증 코드로 액세스·리프레시 토큰 교환."""
    client_id = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            if r.status_code != 200:
                try:
                    err_body = r.text[:500]
                    print(f"[유튜브] Google 토큰 교환 실패 {r.status_code}: {err_body}")
                except Exception:
                    pass
                return None
            return r.json()
    except Exception as e:
        print(f"[유튜브] 토큰 교환 예외: {e!r}")
        return None


async def refresh_access_token(refresh_token: str) -> dict | None:
    """리프레시 토큰으로 새 액세스 토큰 발급."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    async with httpx.AsyncClient() as client:
        r = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        if r.status_code != 200:
            return None
        return r.json()


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _ensure_access_token(access_token: str, refresh_token: str | None) -> str | None:
    """유효한 access_token 반환 (만료 시 refresh)."""
    # 간단 검사: 토큰이 있으면 사용. 실제로는 401 나오면 refresh 시도.
    if access_token:
        return access_token
    if refresh_token:
        data = await refresh_access_token(refresh_token)
        if data and data.get("access_token"):
            return data["access_token"]
    return None


async def get_subscribed_channels(access_token: str, refresh_token: str | None) -> list[dict]:
    """구독 중인 채널 목록 (채널 ID, 제목). 최대 50개."""
    token = await _ensure_access_token(access_token, refresh_token)
    if not token:
        return []
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{YOUTUBE_API_BASE}/subscriptions",
            params={"part": "snippet", "mine": "true", "maxResults": 50},
            headers=_headers(token),
            timeout=15.0,
        )
        if r.status_code == 401 and refresh_token:
            new_data = await refresh_access_token(refresh_token)
            if new_data and new_data.get("access_token"):
                r = await client.get(
                    f"{YOUTUBE_API_BASE}/subscriptions",
                    params={"part": "snippet", "mine": "true", "maxResults": 50},
                    headers=_headers(new_data["access_token"]),
                    timeout=15.0,
                )
        if r.status_code != 200:
            return []
        data = r.json()
        items = data.get("items", [])
        return [
            {
                "channel_id": it["snippet"]["resourceId"]["channelId"],
                "title": it["snippet"]["title"],
            }
            for it in items
        ]


async def get_uploads_playlist_ids(
    client: httpx.AsyncClient, access_token: str, channel_ids: list[str]
) -> dict[str, str]:
    """채널 ID 목록 → 각 채널의 'uploads' 재생목록 ID."""
    if not channel_ids:
        return {}
    token = access_token
    out = {}
    # API는 한 번에 최대 50개 채널
    for i in range(0, len(channel_ids), 50):
        chunk = channel_ids[i : i + 50]
        r = await client.get(
            f"{YOUTUBE_API_BASE}/channels",
            params={"part": "contentDetails", "id": ",".join(chunk)},
            headers=_headers(token),
            timeout=15.0,
        )
        if r.status_code != 200:
            continue
        for it in r.json().get("items", []):
            cid = it["id"]
            uploads_id = (it.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
            if uploads_id:
                out[cid] = uploads_id
    return out


async def get_playlist_videos(
    client: httpx.AsyncClient, access_token: str, playlist_id: str, max_results: int = 5
) -> list[dict]:
    """재생목록의 최신 영상 목록."""
    r = await client.get(
        f"{YOUTUBE_API_BASE}/playlistItems",
        params={
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": max_results,
        },
        headers=_headers(access_token),
        timeout=15.0,
    )
    if r.status_code != 200:
        return []
    items = r.json().get("items", [])
    return [
        {
            "video_id": it["snippet"]["resourceId"].get("videoId"),
            "title": it["snippet"].get("title", ""),
            "published_at": it["snippet"].get("publishedAt", ""),
            "thumbnails": it["snippet"].get("thumbnails", {}),
            "channel_id": it["snippet"].get("channelId", ""),
            "channel_title": it["snippet"].get("channelTitle", ""),
        }
        for it in items
        if it["snippet"]["resourceId"].get("videoId")
    ]


async def fetch_subscription_feed(access_token: str, refresh_token: str | None) -> tuple[list[dict], list[dict], str | None]:
    """
    구독 채널 목록 + 각 채널 최신 영상 수집.
    반환: (channels, videos, new_access_token). videos는 날짜 내림차순 정렬.
    new_access_token: 리프레시로 발급된 새 토큰이 있으면 반환(세션 갱신용), 없으면 None.
    """
    channels = await get_subscribed_channels(access_token, refresh_token)
    if not channels:
        return [], [], None

    token = access_token
    new_token = None
    if refresh_token:
        refreshed = await refresh_access_token(refresh_token)
        if refreshed and refreshed.get("access_token"):
            token = refreshed["access_token"]
            new_token = token
    if not token:
        return channels, [], None

    channel_ids = [c["channel_id"] for c in channels]
    # 채널당 최신 5개, 최대 30채널만 (쿼터·속도 고려)
    channel_ids = channel_ids[:30]
    channel_by_id = {c["channel_id"]: c for c in channels}

    async with httpx.AsyncClient() as client:
        playlist_ids = await get_uploads_playlist_ids(client, token, channel_ids)
        all_videos = []
        for cid, playlist_id in playlist_ids.items():
            vids = await get_playlist_videos(client, token, playlist_id, max_results=5)
            for v in vids:
                v["channel_title"] = (channel_by_id.get(cid) or {}).get("title") or v.get("channel_title", "")
            all_videos.extend(vids)

    # 최신순
    all_videos.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return channels, all_videos, new_token
