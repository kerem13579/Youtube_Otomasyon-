"""Performance analysis: the 3-day news, the drivers, and the publish hour.

Two things worth knowing before reading this:

1. YouTube Analytics has NO hour-of-day dimension. "When did my videos get
   watched" is not answerable from the API. What IS answerable, and what
   actually matters for scheduling, is: given the hour a video was published,
   how well did it do in its first 48 hours. That is what `best_publish_hour`
   learns, from the channel's own uploads.

2. The channel's own 25-video sample says retention is the whole game:
   `İzlemeye devam edenler` correlates with views at r=+0.73, thumbnail CTR
   at r=+0.14. Any "how do I get more views" answer that talks about
   thumbnails before it talks about the first three seconds is wrong here.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .config import ET, cfg
from . import state, youtube

RETENTION_FLOOR = 68.0
MIN_SAMPLE_FOR_HOUR = 8


def _iso_date(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


# ------------------------------------------------------------- the 3-day news

def recent_report(days: int = 3) -> dict:
    """Everything the morning brief needs about the last `days` of uploads."""
    today = datetime.now(timezone.utc).date()
    start = _iso_date(datetime.now(timezone.utc) - timedelta(days=days + 1))
    end = _iso_date(datetime.now(timezone.utc))

    uploads = youtube.my_uploads(limit=50)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    fresh = [v for v in uploads
             if datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")) >= cutoff]

    per_video = {}
    for v in fresh:
        try:
            payload = youtube.analytics(
                start=start, end=end,
                metrics="views,estimatedMinutesWatched,averageViewPercentage,"
                        "averageViewDuration,subscribersGained,likes,shares",
                filters=f"video=={v['id']}")
            rows = youtube.rows_as_dicts(payload)
            per_video[v["id"]] = rows[0] if rows else {}
        except Exception as exc:  # analytics lags ~48h for very new videos
            per_video[v["id"]] = {"_error": str(exc)[:120]}

    try:
        channel = youtube.rows_as_dicts(youtube.analytics(
            start=start, end=end,
            metrics="views,estimatedMinutesWatched,subscribersGained",
            dimensions="day"))
    except Exception:
        channel = []

    return {
        "videos": fresh,
        "per_video": per_video,
        "channel_by_day": channel,
        "window_days": days,
    }


# ------------------------------------------------------------- what drives views

def drivers(sample: int = 40) -> dict:
    """Recompute the factor analysis across everything on the channel."""
    uploads = youtube.my_uploads(limit=sample)
    if len(uploads) < 5:
        return {"ready": False, "reason": "not enough uploads yet"}

    start = _iso_date(datetime.now(timezone.utc) - timedelta(days=365))
    end = _iso_date(datetime.now(timezone.utc))
    try:
        rows = youtube.rows_as_dicts(youtube.analytics(
            start=start, end=end,
            metrics="views,averageViewPercentage,averageViewDuration",
            dimensions="video", sort="-views", max_results=200))
    except Exception as exc:
        return {"ready": False, "reason": f"analytics unavailable: {exc}"}

    by_id = {r["video"]: r for r in rows}
    merged = []
    for v in uploads:
        a = by_id.get(v["id"])
        if not a:
            continue
        merged.append({
            "id": v["id"],
            "title": v["title"],
            "views": a.get("views", v["views"]),
            "avg_pct": a.get("averageViewPercentage", 0.0),
            "avg_dur": a.get("averageViewDuration", 0),
            "duration_s": _iso8601_seconds(v["duration"]),
            "published_at": v["published_at"],
        })
    if len(merged) < 5:
        return {"ready": False, "reason": "no overlap between uploads and analytics"}

    by_pct = sorted(merged, key=lambda m: m["avg_pct"])
    half = len(by_pct) // 2
    low, high = by_pct[:half], by_pct[half:]

    # Duration bands: the channel's 33s+ uploads all sit at the bottom.
    short = [m for m in merged if m["duration_s"] <= 31]
    long_ = [m for m in merged if m["duration_s"] > 31]

    return {
        "ready": True,
        "n": len(merged),
        "median_views": statistics.median([m["views"] for m in merged]),
        "retention_low_median": statistics.median([m["views"] for m in low]) if low else 0,
        "retention_high_median": statistics.median([m["views"] for m in high]) if high else 0,
        "retention_split_at": round(by_pct[half]["avg_pct"], 1) if half < len(by_pct) else 0,
        "short_median": statistics.median([m["views"] for m in short]) if short else 0,
        "long_median": statistics.median([m["views"] for m in long_]) if long_ else 0,
        "short_n": len(short),
        "long_n": len(long_),
        "top": sorted(merged, key=lambda m: -m["views"])[:5],
        "bottom": sorted(merged, key=lambda m: m["views"])[:5],
    }


def _iso8601_seconds(duration: str) -> int:
    """PT1M2S -> 62. Good enough for Shorts."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


# ---------------------------------------------------------- the publish hour

def best_publish_hour(sample: int = 40) -> dict:
    """Learn the publish hour (US Eastern) that produced the best first 48h.

    Falls back to the seed hour until there are enough uploads to mean
    anything. Returns {hour_et, sample_size, learned, per_hour}.
    """
    learnings = state.load("learnings")
    uploads = youtube.my_uploads(limit=sample)
    scored: list[tuple[int, int]] = []

    for v in uploads:
        published = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - published
        if age < timedelta(days=3):
            continue  # not yet settled
        start = _iso_date(published)
        end = _iso_date(published + timedelta(days=2))
        try:
            rows = youtube.rows_as_dicts(youtube.analytics(
                start=start, end=end, metrics="views",
                filters=f"video=={v['id']}"))
        except Exception:
            continue
        if not rows:
            continue
        first48 = rows[0].get("views", 0)
        scored.append((published.astimezone(ET).hour, first48))

    if len(scored) < MIN_SAMPLE_FOR_HOUR:
        return {
            "hour_et": cfg.seed_publish_hour_et,
            "sample_size": len(scored),
            "learned": False,
            "per_hour": {},
        }

    buckets: dict[int, list[int]] = defaultdict(list)
    for hour, views in scored:
        buckets[hour].append(views)

    # Median, not mean: one 644K outlier should not pick the schedule.
    per_hour = {h: statistics.median(v) for h, v in buckets.items() if len(v) >= 2}
    if not per_hour:
        per_hour = {h: statistics.median(v) for h, v in buckets.items()}

    best = max(per_hour, key=per_hour.get)
    learnings.update({
        "best_publish_hour_et": best,
        "sample_size": len(scored),
        "updated_at": state.now_iso(),
        "per_hour_median_views": {str(k): v for k, v in sorted(per_hour.items())},
    })
    state.save("learnings", learnings)
    return {"hour_et": best, "sample_size": len(scored), "learned": True,
            "per_hour": per_hour}


def next_publish_slot(hour_et: int, min_lead_minutes: int = 45) -> datetime:
    """The next occurrence of `hour_et` in US Eastern, as a UTC datetime."""
    now_et = datetime.now(ET)
    slot = now_et.replace(hour=hour_et, minute=0, second=0, microsecond=0)
    if slot <= now_et + timedelta(minutes=min_lead_minutes):
        slot += timedelta(days=1)
    return slot.astimezone(timezone.utc)
