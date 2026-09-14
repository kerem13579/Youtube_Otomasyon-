"""WaveSpeed submit + poll, written defensively around the response shape.

WaveSpeed returns results under data.outputs on most models, but a few put
the file under data.output or data.video. Rather than guess, `_find_video`
walks the whole payload for the first .mp4 URL.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from .config import cfg

POLL_EVERY = 10
POLL_TIMEOUT = 1800  # 30 minutes; a 30s Seedance render is usually 3-8


def _auth() -> dict:
    return {"Authorization": f"Bearer {cfg.ws_key}",
            "Content-Type": "application/json"}


def image_to_data_uri(path: Path) -> str:
    raw = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    return f"data:image/{mime};base64,{raw}"


def submit(prompt: str, *, duration: int = 30, aspect_ratio: str = "9:16",
           resolution: str = "480p", images: list[str] | None = None,
           enable_audio: bool = True, seed: int | None = None,
           extra: dict | None = None) -> str:
    """Submit a generation. Returns the task id."""
    payload: dict = {
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        # The skill's hardest-won lesson: audio defaults OFF and a silent
        # render wastes the whole generation.
        "enable_audio": enable_audio,
        "generate_audio": enable_audio,
    }
    if images:
        payload["images"] = images
        payload["reference_images"] = images
    if seed is not None:
        payload["seed"] = seed
    if extra:
        payload.update(extra)

    url = f"{cfg.ws_base}/{cfg.ws_model}"
    r = requests.post(url, headers=_auth(), json=payload, timeout=180)
    if r.status_code not in (200, 201):
        raise RuntimeError(
            f"WaveSpeed submit failed ({r.status_code}) for model "
            f"'{cfg.ws_model}': {r.text[:500]}"
        )
    data = r.json().get("data", r.json())
    task_id = data.get("id") or data.get("task_id")
    if not task_id:
        raise RuntimeError(f"WaveSpeed gave no task id: {r.text[:400]}")
    return task_id


def _find_video(node) -> str | None:
    """Depth-first search for the first video URL anywhere in the payload."""
    if isinstance(node, str):
        low = node.lower()
        if low.startswith("http") and (".mp4" in low or ".webm" in low
                                       or ".mov" in low):
            return node
        return None
    if isinstance(node, dict):
        for value in node.values():
            found = _find_video(value)
            if found:
                return found
    if isinstance(node, list):
        for value in node:
            found = _find_video(value)
            if found:
                return found
    return None


def wait(task_id: str, timeout: int = POLL_TIMEOUT) -> str:
    """Poll until the task completes. Returns the output video URL."""
    url = f"{cfg.ws_base}/predictions/{task_id}/result"
    deadline = time.time() + timeout
    last_status = "unknown"
    while time.time() < deadline:
        r = requests.get(url, headers=_auth(), timeout=90)
        if r.status_code != 200:
            time.sleep(POLL_EVERY)
            continue
        data = r.json().get("data", r.json())
        last_status = (data.get("status") or "").lower()
        if last_status in ("completed", "succeeded", "success"):
            video = _find_video(data)
            if not video:
                raise RuntimeError(
                    f"WaveSpeed reported success but returned no video URL: "
                    f"{str(data)[:500]}")
            return video
        if last_status in ("failed", "error", "cancelled", "canceled"):
            raise RuntimeError(
                f"WaveSpeed generation failed: {data.get('error') or str(data)[:400]}")
        time.sleep(POLL_EVERY)
    raise TimeoutError(
        f"WaveSpeed task {task_id} still '{last_status}' after {timeout}s")


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=900) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    if dest.stat().st_size < 50_000:
        raise RuntimeError(f"Downloaded video is suspiciously small: {dest.stat().st_size} bytes")
    return dest


def generate(prompt: str, dest: Path, **kwargs) -> Path:
    task_id = submit(prompt, **kwargs)
    url = wait(task_id)
    return download(url, dest)
