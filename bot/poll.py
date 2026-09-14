"""Reads Telegram, acts on the button press. Runs every 5 minutes."""
from __future__ import annotations

from . import ideas, pipeline, state, telegram


def handle_callback(update: dict, st: dict) -> bool:
    """Return True if a pipeline was started (so the caller stops consuming)."""
    cq = update["callback_query"]
    data = cq.get("data", "")
    telegram.answer_callback(cq["id"])

    pending = st.get("pending_ideas") or []
    message_id = st.get("pending_message_id")

    if data == "regen":
        telegram.edit(message_id, "🔄 Yeni fikirler üretiliyor…", buttons=[])
        rejected = st.setdefault("rejected", [])
        rejected.extend(pending)
        st["rejected"] = rejected[-40:]
        fresh = ideas.generate(n=5)
        telegram.edit(message_id, ideas.format_for_telegram(fresh),
                      buttons=telegram.idea_keyboard(len(fresh)))
        st["pending_ideas"] = fresh
        state.save("state", st)
        return False

    if data.startswith("pick:"):
        index = int(data.split(":", 1)[1])
        if index >= len(pending):
            telegram.send("⚠️ Bu fikir listesi artık geçerli değil, sabahki mesajı bekle.")
            return False
        if st.get("busy"):
            telegram.send("⏳ Zaten bir video üretiliyor, o bitince tekrar dene.")
            return False

        chosen = pending[index]
        st["busy"] = True
        st["pending_ideas"] = []
        # the four ideas not taken are still "seen" - never offer them again
        st.setdefault("rejected", []).extend(
            [p for i, p in enumerate(pending) if i != index])
        st["rejected"] = st["rejected"][-40:]
        state.save("state", st)

        telegram.edit(
            message_id,
            f"✅ Seçildi: <b>{chosen['object_singular']} → {chosen.get('result')}</b>",
            buttons=[])
        pipeline.run_guarded(chosen)
        return True

    return False


def main() -> None:
    st = state.load("state")
    offset = st.get("last_update_id", 0) + 1
    updates = telegram.get_updates(offset)
    if not updates:
        return

    started = False
    for update in updates:
        st["last_update_id"] = max(st.get("last_update_id", 0), update["update_id"])
        state.save("state", st)
        if started:
            continue  # a pipeline is running; the rest wait for the next tick
        if "callback_query" in update:
            st = state.load("state")
            st["last_update_id"] = update["update_id"]
            started = handle_callback(update, st)
        elif "message" in update:
            text = (update["message"].get("text") or "").strip().lower()
            if text in ("/fikir", "/ideas", "fikir"):
                fresh = ideas.generate(n=5)
                msg = telegram.send(ideas.format_for_telegram(fresh),
                                    buttons=telegram.idea_keyboard(len(fresh)))
                st = state.load("state")
                st["pending_ideas"] = fresh
                st["pending_message_id"] = msg["message_id"]
                state.save("state", st)
            elif text in ("/durum", "/status"):
                queue = state.load("state").get("queue", [])
                if queue:
                    lines = [f"• {q['title'][:50]} → {q['publish_at_utc']}" for q in queue]
                    telegram.send("📋 <b>Yayın kuyruğu</b>\n" + "\n".join(lines))
                else:
                    telegram.send("📋 Kuyruk boş.")


if __name__ == "__main__":
    main()
