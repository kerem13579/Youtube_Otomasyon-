#!/usr/bin/env python3
"""Check every credential and every moving part, without publishing anything.

    python -m tools.selftest

Run it from the Actions tab (workflow_dispatch on "Self test") the first time
you set the secrets up. It touches Telegram, the LLM, YouTube and WaveSpeed,
and renders the bumper over a throwaway clip so you can see the overlay.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def wrap(fn):
        try:
            detail = fn() or "ok"
            RESULTS.append((name, True, str(detail)[:200]))
        except Exception as exc:
            RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"[:300]))
        return fn
    return wrap


def main() -> int:
    from bot import editor, telegram, youtube
    from bot.config import ASSETS

    @check("Telegram")
    def _tg():
        telegram.send("🧪 Self-test çalışıyor…")
        return "mesaj gönderildi"

    @check("LLM")
    def _llm():
        from bot import llm
        out = llm.ask("Reply with the single word OK.", "Go", max_tokens=16)
        return f"{llm.provider()} / {llm.model()} -> {out.strip()[:24]}"

    @check("YouTube auth")
    def _yt():
        uploads = youtube.my_uploads(limit=5)
        return f"{len(uploads)} video okundu, en yenisi: {uploads[0]['title'][:40]}"

    @check("YouTube Analytics")
    def _yt_analytics():
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
        rows = youtube.rows_as_dicts(youtube.analytics(start, end, "views"))
        return f"son 14 gün: {rows[0].get('views') if rows else '?'} görüntülenme"

    @check("WaveSpeed key")
    def _ws():
        import requests
        from bot.config import cfg
        r = requests.get(f"{cfg.ws_base}/predictions/selftest-nonexistent/result",
                         headers={"Authorization": f"Bearer {cfg.ws_key}"}, timeout=60)
        if r.status_code in (401, 403):
            raise RuntimeError(f"anahtar reddedildi ({r.status_code})")
        return f"anahtar kabul edildi (HTTP {r.status_code})"

    @check("ffmpeg + bumper")
    def _edit():
        tmp = Path(tempfile.mkdtemp())
        base = tmp / "base.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=0x6b5a48:size=1080x1920:duration=30:rate=30",
            "-f", "lavfi", "-i", "anoisesrc=d=30:c=pink:a=0.02",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(base)], check=True, capture_output=True)
        out = editor.finish(base, tmp / "out.mp4")
        info = editor.probe(out)
        telegram.send_video(out, caption="🧪 Bindirme testi — abone ol katmanı böyle görünüyor.")
        return f"{info['width']}x{info['height']}, {info['duration']:.1f}s"

    @check("Rotation data")
    def _rot():
        from bot import metadata, state
        history = state.load("history")
        pat = metadata.pick_title_pattern(history)
        title = metadata.render_title(pat, "shopping trolley", "shopping trolleys", "planters")
        tags = metadata.build_tags("water_feature")
        return (f"{pat['id']} -> \"{title}\" ({len(title)} krktr) · "
                f"{len(tags)} etiket / {metadata.tags_length(tags)} krktr")

    ok = all(passed for _, passed, _ in RESULTS)
    lines = ["🧪 <b>Self-test sonucu</b>", ""]
    for name, passed, detail in RESULTS:
        lines.append(f"{'✅' if passed else '❌'} <b>{name}</b> — {detail}")
    lines.append("")
    lines.append("Hepsi yeşilse sistem hazır." if ok else "Kırmızıları düzelt, sonra tekrar çalıştır.")
    body = "\n".join(lines)

    try:
        telegram.send(body)
    except Exception:
        pass
    print(body.replace("<b>", "").replace("</b>", ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
