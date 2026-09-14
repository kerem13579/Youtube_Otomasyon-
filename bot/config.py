"""Central configuration. Everything secret comes from the environment."""
from __future__ import annotations
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
WORK = ROOT / ".work"

TR = ZoneInfo("Europe/Istanbul")
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def _req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(
            f"Missing required secret {name}. Add it under "
            f"Settings -> Secrets and variables -> Actions in the GitHub repo."
        )
    return v


def _opt(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip() or default


class Config:
    # --- Telegram ---
    tg_token = property(lambda s: _req("TELEGRAM_BOT_TOKEN"))
    tg_chat = property(lambda s: _req("TELEGRAM_CHAT_ID"))

    # --- LLM (idea + prompt + metadata writing) ---
    # Provider and model live in bot/llm.py; see LLM_PROVIDER / LLM_MODEL.

    # --- WaveSpeed (video generation) ---
    ws_key = property(lambda s: _req("WAVESPEED_API_KEY"))
    ws_model = property(lambda s: _opt("WAVESPEED_MODEL", "bytedance/seedance-v2-pro"))
    ws_base = property(lambda s: _opt("WAVESPEED_BASE", "https://api.wavespeed.ai/api/v3"))

    # --- YouTube ---
    yt_client_id = property(lambda s: _req("YT_CLIENT_ID"))
    yt_client_secret = property(lambda s: _req("YT_CLIENT_SECRET"))
    yt_refresh_token = property(lambda s: _req("YT_REFRESH_TOKEN"))
    yt_channel_id = property(lambda s: _opt("YT_CHANNEL_ID", "UC-BXtsxzWD-QyWotA7J88aA"))

    # --- Behaviour ---
    # Seed publish window in US Eastern; replaced by measured data once
    # the channel has enough videos (see analytics.best_publish_hour).
    seed_publish_hour_et = property(lambda s: int(_opt("SEED_PUBLISH_HOUR_ET", "16")))
    # Videos must be at least this long / short (seconds). Data: 33s+ always underperforms.
    target_duration = property(lambda s: int(_opt("TARGET_DURATION", "30")))
    # Retention threshold learned from channel data.
    retention_floor = 68.0
    # Don't reuse a title pattern seen in the last N uploads.
    title_pattern_cooldown = 12
    title_family_cooldown = 4
    desc_pattern_cooldown = 6
    dry_run = property(lambda s: _opt("DRY_RUN", "0") == "1")


cfg = Config()
