"""Idea -> prompt -> video -> bumper -> upload -> scheduled publish."""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path

from .config import ASSETS, ET, TR, cfg
from . import (analytics, editor, metadata, prompts, state, telegram,
               wavespeed, youtube)

AVATAR_NOTE = (
    "Lock her face, hair, skin tone, body type and the exact outfit shown in "
    "the reference image for the entire 30 seconds. No wardrobe change, no "
    "aging, no face drift between cuts."
)


def run(idea: dict) -> dict:
    """Full pipeline for one approved idea. Raises on any hard failure."""
    work = editor.workdir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw = work / f"{stamp}-raw.mp4"
    final = work / f"{stamp}-final.mp4"

    history = state.load("history")

    telegram.send(
        f"⚙️ <b>{idea['object_singular']} → {idea.get('result')}</b>\n"
        f"Prompt yazılıyor…")

    # 1. the generation prompt and the metadata parts ----------------------
    video_prompt = prompts.write_video_prompt(idea, AVATAR_NOTE)
    parts = prompts.write_metadata_parts(idea, video_prompt)

    # 2. title, description, tags - all rotation-checked -------------------
    category = parts.get("result_category", "planter").replace("_", " ")
    category_plural = category if category.endswith("s") else category + "s"
    plural = idea.get("object_plural") or (idea["object_singular"] + "s")

    def _compose() -> tuple[dict, str, list[str]]:
        pat = metadata.pick_title_pattern(history)
        text = metadata.render_title(pat, idea["object_singular"], plural,
                                     category_plural)
        issues = metadata.validate_title(
            text, parts.get("result_words", []),
            allow=(category, category_plural))
        return pat, text, issues

    pattern, title, problems = _compose()
    for _ in range(3):           # a bad draw is cheap to redo; a bad title is not
        if not problems:
            break
        pattern, title, problems = _compose()

    description, desc_id, question = metadata.build_description(
        history,
        obj=idea["object_singular"],
        result_category=idea.get("result", "garden piece"),
        build_detail=parts.get("build_detail", ""),
        sounds=parts.get("sounds", "the wet cement, the trowel and the birds"))
    tags = metadata.build_tags(parts.get("result_category", "planter"))

    # 3. generate ----------------------------------------------------------
    telegram.send(f"🎬 Video üretiliyor (WaveSpeed)…\nBaşlık: <code>{title}</code>")
    avatar = ASSETS / "avatar_reference.png"
    images = [wavespeed.image_to_data_uri(avatar)] if avatar.exists() else None
    wavespeed.generate(
        prompts.flatten_for_wavespeed(video_prompt),
        raw,
        duration=cfg.target_duration,
        aspect_ratio="9:16",
        resolution="480p",
        images=images,
        enable_audio=True,
    )

    # 4. bumper + upscale --------------------------------------------------
    telegram.send("✂️ Abone ol bindiriliyor ve upscale ediliyor…")
    editor.finish(raw, final)
    silent = editor.audio_is_silent(final)

    # 5. upload private ----------------------------------------------------
    video_id = youtube.upload(final, title, description, tags, privacy="private")

    # 6. schedule the flip to public --------------------------------------
    hour = analytics.best_publish_hour()
    slot_utc = analytics.next_publish_slot(hour["hour_et"])

    st = state.load("state")
    st.setdefault("queue", []).append({
        "video_id": video_id,
        "title": title,
        "publish_at_utc": slot_utc.isoformat(),
        "object": idea["object_singular"],
        "created_at": state.now_iso(),
    })
    state.save("state", st)

    metadata.record_upload(history, {
        "video_id": video_id,
        "title": title,
        "title_pattern": pattern["id"],
        "title_family": pattern["family"],
        "desc_pattern": desc_id,
        "desc_question": question,
        "object": idea["object_singular"],
        "result": idea.get("result"),
        "tier": idea.get("tier"),
        "result_category": parts.get("result_category"),
        "uploaded_at": state.now_iso(),
        "publish_at_utc": slot_utc.isoformat(),
    })

    # 7. report ------------------------------------------------------------
    slot_et = slot_utc.astimezone(ET)
    slot_tr = slot_utc.astimezone(TR)
    warn = "\n⚠️ <b>Ses sessiz görünüyor</b> — kontrol et." if silent else ""
    problem_line = ("\n⚠️ Başlık kuralı: " + "; ".join(problems)) if problems else ""
    telegram.send_video(final, caption=(
        f"✅ <b>{title}</b>\n"
        f"Yüklendi (gizli) · yayın: {slot_et:%d %b %H:%M} ET / {slot_tr:%H:%M} TR"
        f"{warn}{problem_line}"))
    telegram.send(
        f"<b>Açıklama</b>\n<pre>{_esc(description)}</pre>\n"
        f"<b>Etiketler</b> ({metadata.tags_length(tags)} karakter, {len(tags)} adet)\n"
        f"<pre>{_esc(', '.join(tags))}</pre>\n"
        f"Kalıp: {pattern['id']} ({pattern['family']}) · açıklama {desc_id}")

    return {"video_id": video_id, "title": title, "publish_at_utc": slot_utc.isoformat()}


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def run_guarded(idea: dict) -> None:
    """Never let a failure die silently inside a cron run."""
    try:
        run(idea)
    except Exception as exc:
        telegram.send(
            f"❌ <b>Pipeline durdu</b>\n<code>{_esc(str(exc))[:900]}</code>")
        traceback.print_exc()
        raise
    finally:
        st = state.load("state")
        st["busy"] = False
        state.save("state", st)
