"""Flips queued videos from private to public at their exact target minute.

Not YouTube's own scheduler: the video sits private and this job makes it
public at the chosen second. GitHub's cron can fire a few minutes late, so
this runs every 15 minutes, picks up anything due within the next 25, and
sleeps to the exact timestamp before flipping.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from .config import ET, TR
from . import state, telegram, youtube

LOOKAHEAD = timedelta(minutes=25)
MAX_SLEEP = 30 * 60


def main() -> None:
    st = state.load("state")
    queue = st.get("queue", [])
    if not queue:
        return

    now = datetime.now(timezone.utc)
    remaining = []
    for item in queue:
        due = datetime.fromisoformat(item["publish_at_utc"])
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)

        if due > now + LOOKAHEAD:
            remaining.append(item)
            continue

        wait = (due - datetime.now(timezone.utc)).total_seconds()
        if wait > MAX_SLEEP:
            remaining.append(item)
            continue
        if wait > 0:
            time.sleep(wait)

        try:
            youtube.set_privacy(item["video_id"], "public")
        except Exception as exc:
            telegram.send(
                f"❌ <b>Yayınlanamadı</b>: {item['title'][:60]}\n"
                f"<code>{str(exc)[:400]}</code>\n"
                f"Bir sonraki turda tekrar denenecek.")
            remaining.append(item)
            continue

        url = youtube.video_url(item["video_id"])
        published = datetime.now(timezone.utc)
        telegram.send(
            f"🚀 <b>Yayında</b>\n{item['title']}\n"
            f"{published.astimezone(ET):%H:%M} ET · "
            f"{published.astimezone(TR):%H:%M} TR\n{url}",
            disable_preview=False)

        history = state.load("history")
        for entry in history.get("videos", []):
            if entry.get("video_id") == item["video_id"]:
                entry["published_at"] = published.isoformat(timespec="seconds")
                entry["published_hour_et"] = published.astimezone(ET).hour
        state.save("history", history)

    st["queue"] = remaining
    state.save("state", st)


if __name__ == "__main__":
    main()
