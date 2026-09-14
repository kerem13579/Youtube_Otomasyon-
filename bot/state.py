"""Repo-backed JSON state. The workflow commits data/ back after each run."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any

from .config import DATA

_FILES = {
    "state": DATA / "state.json",
    "history": DATA / "history.json",
    "title_patterns": DATA / "title_patterns.json",
    "desc_patterns": DATA / "desc_patterns.json",
    "learnings": DATA / "learnings.json",
}

_DEFAULTS: dict[str, Any] = {
    "state": {
        "pending_ideas": [],       # the 5 ideas last sent to Telegram
        "pending_message_id": None,
        "last_update_id": 0,       # Telegram getUpdates offset
        "queue": [],               # videos uploaded, waiting for their publish slot
        "last_brief_date": None,
        "busy": False,             # guards against two pipelines at once
    },
    "history": {"videos": []},     # every published video + what we knew about it
    "learnings": {
        "best_publish_hour_et": None,
        "sample_size": 0,
        "updated_at": None,
        "notes": [],
    },
}


def load(name: str) -> Any:
    path = _FILES[name]
    if not path.exists():
        return json.loads(json.dumps(_DEFAULTS.get(name, {})))
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save(name: str, payload: Any) -> None:
    path = _FILES[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
