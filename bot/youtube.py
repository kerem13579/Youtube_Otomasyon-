"""YouTube Data API v3 + YouTube Analytics API, over plain HTTP.

No google client libraries: a refresh token, requests, and a resumable
upload is all this needs, and it keeps the Actions runner install tiny.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .config import cfg

TOKEN_URL = "https://oauth2.googleapis.com/token"
DATA_API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3/videos"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"

_token_cache: dict[str, Any] = {}


def access_token() -> str:
    """Exchange the long-lived refresh token for a short-lived access token."""
    now = datetime.now(timezone.utc)
    if _token_cache.get("expires_at", now) > now + timedelta(seconds=60):
        return _token_cache["token"]

    r = requests.post(TOKEN_URL, data={
        "client_id": cfg.yt_client_id,
        "client_secret": cfg.yt_client_secret,
        "refresh_token": cfg.yt_refresh_token,
        "grant_type": "refresh_token",
    }, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            "YouTube token refresh failed. The refresh token is usually the "
            f"problem - regenerate it with tools/get_youtube_token.py. {r.text[:300]}"
        )
    body = r.json()
    _token_cache["token"] = body["access_token"]
    _token_cache["expires_at"] = now + timedelta(seconds=body.get("expires_in", 3500))
    return _token_cache["token"]


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {access_token()}"}
    if extra:
        h.update(extra)
    return h


# ------------------------------------------------------------------ read

def my_uploads(limit: int = 50) -> list[dict]:
    """Every video on the channel, newest first, with exact publish times."""
    ch = requests.get(f"{DATA_API}/channels", headers=_headers(), params={
        "part": "contentDetails", "mine": "true"}, timeout=60)
    ch.raise_for_status()
    items = ch.json().get("items", [])
    if not items:
        return []
    playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids: list[str] = []
    page = None
    while len(ids) < limit:
        r = requests.get(f"{DATA_API}/playlistItems", headers=_headers(), params={
            "part": "contentDetails", "playlistId": playlist,
            "maxResults": 50, "pageToken": page}, timeout=60)
        r.raise_for_status()
        body = r.json()
        ids += [i["contentDetails"]["videoId"] for i in body.get("items", [])]
        page = body.get("nextPageToken")
        if not page:
            break

    out: list[dict] = []
    for chunk in [ids[i:i + 50] for i in range(0, min(len(ids), limit), 50)]:
        r = requests.get(f"{DATA_API}/videos", headers=_headers(), params={
            "part": "snippet,statistics,contentDetails,status",
            "id": ",".join(chunk)}, timeout=60)
        r.raise_for_status()
        for v in r.json().get("items", []):
            out.append({
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published_at": v["snippet"]["publishedAt"],
                "tags": v["snippet"].get("tags", []),
                "duration": v["contentDetails"]["duration"],
                "privacy": v["status"]["privacyStatus"],
                "views": int(v["statistics"].get("viewCount", 0)),
                "likes": int(v["statistics"].get("likeCount", 0)),
                "comments": int(v["statistics"].get("commentCount", 0)),
            })
    out.sort(key=lambda v: v["published_at"], reverse=True)
    return out


def analytics(start: str, end: str, metrics: str, dimensions: str = "",
              filters: str = "", sort: str = "", max_results: int = 0) -> dict:
    params: dict[str, Any] = {
        "ids": f"channel=={cfg.yt_channel_id}",
        "startDate": start, "endDate": end, "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if filters:
        params["filters"] = filters
    if sort:
        params["sort"] = sort
    if max_results:
        params["maxResults"] = max_results
    r = requests.get(ANALYTICS_API, headers=_headers(), params=params, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube Analytics failed: {r.status_code} {r.text[:300]}")
    return r.json()


def rows_as_dicts(payload: dict) -> list[dict]:
    cols = [c["name"] for c in payload.get("columnHeaders", [])]
    return [dict(zip(cols, row)) for row in payload.get("rows", [])]


# ----------------------------------------------------------------- write

def upload(path: Path, title: str, description: str, tags: list[str],
           privacy: str = "private", category_id: str = "26",
           made_for_kids: bool = False) -> str:
    """Resumable upload. Returns the new video id."""
    size = os.path.getsize(path)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    start = requests.post(
        UPLOAD_API,
        headers=_headers({
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": "video/mp4",
        }),
        params={"uploadType": "resumable", "part": "snippet,status"},
        json=body, timeout=120,
    )
    if start.status_code not in (200, 201):
        raise RuntimeError(f"Upload init failed: {start.status_code} {start.text[:400]}")
    session_url = start.headers["Location"]

    with open(path, "rb") as fh:
        put = requests.put(
            session_url,
            headers={"Content-Length": str(size), "Content-Type": "video/mp4"},
            data=fh, timeout=1800,
        )
    if put.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed: {put.status_code} {put.text[:400]}")
    return put.json()["id"]


def set_privacy(video_id: str, privacy: str) -> None:
    r = requests.put(
        f"{DATA_API}/videos",
        headers=_headers({"Content-Type": "application/json"}),
        params={"part": "status"},
        json={"id": video_id, "status": {"privacyStatus": privacy,
                                         "selfDeclaredMadeForKids": False}},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Privacy change failed: {r.status_code} {r.text[:300]}")


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"
