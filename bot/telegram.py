"""Thin Telegram Bot API client — send, edit, buttons, video upload, polling."""
from __future__ import annotations
import json
from typing import Any

import requests

from .config import cfg

TIMEOUT = 120


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{cfg.tg_token}/{method}"


def _call(method: str, **params) -> dict:
    r = requests.post(_url(method), json=params, timeout=TIMEOUT)
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {body}")
    return body["result"]


def send(text: str, buttons: list[list[dict]] | None = None,
         disable_preview: bool = True) -> dict:
    params: dict[str, Any] = {
        "chat_id": cfg.tg_chat,
        "text": text[:4096],
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": disable_preview},
    }
    if buttons:
        params["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendMessage", **params)


def edit(message_id: int, text: str, buttons: list[list[dict]] | None = None) -> dict:
    params: dict[str, Any] = {
        "chat_id": cfg.tg_chat,
        "message_id": message_id,
        "text": text[:4096],
        "parse_mode": "HTML",
    }
    if buttons is not None:
        params["reply_markup"] = {"inline_keyboard": buttons}
    try:
        return _call("editMessageText", **params)
    except RuntimeError as exc:
        # "message is not modified" is harmless
        if "not modified" in str(exc):
            return {}
        raise


def answer_callback(callback_id: str, text: str = "") -> None:
    try:
        _call("answerCallbackQuery", callback_query_id=callback_id, text=text[:200])
    except RuntimeError:
        pass  # a stale callback id is not worth failing a run over


def send_video(path, caption: str = "") -> dict:
    """Telegram caps captions at 1024 chars — the caller keeps it short."""
    with open(path, "rb") as fh:
        r = requests.post(
            _url("sendVideo"),
            data={"chat_id": cfg.tg_chat, "caption": caption[:1024],
                  "parse_mode": "HTML", "supports_streaming": "true"},
            files={"video": fh},
            timeout=600,
        )
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram sendVideo failed: {body}")
    return body["result"]


def get_updates(offset: int, timeout: int = 0) -> list[dict]:
    r = requests.get(
        _url("getUpdates"),
        params={"offset": offset, "timeout": timeout,
                "allowed_updates": json.dumps(["callback_query", "message"])},
        timeout=timeout + 30,
    )
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {body}")
    return body["result"]


def idea_keyboard(count: int) -> list[list[dict]]:
    row = [{"text": f"{i + 1}", "callback_data": f"pick:{i}"} for i in range(count)]
    return [row, [{"text": "🔄 Yeni 5 fikir", "callback_data": "regen"}]]
