"""06:00 Europe/Istanbul: the news, the drivers, and five fresh ideas."""
from __future__ import annotations

from datetime import datetime, timezone

from .config import ET, TR
from . import analytics, ideas, state, telegram


def _fmt_int(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "?"


def news_block() -> str:
    try:
        report = analytics.recent_report(days=3)
    except Exception as exc:
        return f"📊 <b>Son 3 gün</b>\n<i>Analitik çekilemedi: {str(exc)[:160]}</i>\n"

    lines = ["📊 <b>Son 3 günün videoları</b>"]
    if not report["videos"]:
        lines.append("<i>Son 3 günde yayınlanmış video yok.</i>")
    for v in report["videos"]:
        stats = report["per_video"].get(v["id"], {})
        if "_error" in stats:
            lines.append(f"• <b>{v['title'][:52]}</b>\n  <i>veri henüz gelmedi</i>")
            continue
        views = _fmt_int(stats.get("views", v.get("views", 0)))
        avg = stats.get("averageViewPercentage")
        avg_txt = f" · izlenme %{avg:.0f}" if isinstance(avg, (int, float)) else ""
        subs = stats.get("subscribersGained", 0)
        lines.append(
            f"• <b>{v['title'][:52]}</b>\n"
            f"  {views} görüntülenme{avg_txt} · +{_fmt_int(subs)} abone")

    by_day = report.get("channel_by_day") or []
    if by_day:
        tail = " · ".join(f"{r['day'][5:]}: {_fmt_int(r['views'])}" for r in by_day[-4:])
        lines.append(f"\n<b>Kanal günlük:</b> {tail}")
    return "\n".join(lines) + "\n"


def drivers_block() -> str:
    try:
        d = analytics.drivers()
    except Exception as exc:
        return f"🔍 <b>Ne işe yarıyor</b>\n<i>Hesaplanamadı: {str(exc)[:140]}</i>\n"
    if not d.get("ready"):
        return f"🔍 <b>Ne işe yarıyor</b>\n<i>{d.get('reason')}</i>\n"

    lines = ["🔍 <b>İzlenmeyi ne belirliyor</b> (tüm videolar)"]
    lines.append(
        f"• Retention üst yarı: <b>{_fmt_int(d['retention_high_median'])}</b> medyan "
        f"· alt yarı: <b>{_fmt_int(d['retention_low_median'])}</b> "
        f"(ayrım %{d['retention_split_at']})")
    if d["long_n"]:
        lines.append(
            f"• ≤31 sn: <b>{_fmt_int(d['short_median'])}</b> medyan ({d['short_n']} video) "
            f"· 31 sn üstü: <b>{_fmt_int(d['long_median'])}</b> ({d['long_n']} video)")
    top = d["top"][0] if d["top"] else None
    if top:
        lines.append(f"• En iyi: {top['title'][:46]} — {_fmt_int(top['views'])}")
    return "\n".join(lines) + "\n"


def schedule_block() -> str:
    try:
        hour = analytics.best_publish_hour()
    except Exception as exc:
        return f"🕐 <b>Yayın saati</b>\n<i>Hesaplanamadı: {str(exc)[:140]}</i>\n"
    slot = analytics.next_publish_slot(hour["hour_et"])
    et = slot.astimezone(ET)
    tr = slot.astimezone(TR)
    if hour["learned"]:
        src = f"kanalın kendi {hour['sample_size']} videosundan öğrenildi"
    else:
        src = f"başlangıç değeri ({hour['sample_size']}/8 video, henüz öğrenmedi)"
    return (f"🕐 <b>Bugünün yayın saati</b>\n"
            f"{et:%H:%M} ET = {tr:%H:%M} TR · <i>{src}</i>\n")


def main() -> None:
    st = state.load("state")
    today = datetime.now(TR).date().isoformat()

    header = (f"☀️ <b>Günaydın</b> · {datetime.now(TR):%d %B %Y}\n\n"
              + news_block() + "\n" + drivers_block() + "\n" + schedule_block())
    telegram.send(header)

    five = ideas.generate(n=5)
    msg = telegram.send(ideas.format_for_telegram(five),
                        buttons=telegram.idea_keyboard(len(five)))

    st["pending_ideas"] = five
    st["pending_message_id"] = msg["message_id"]
    st["last_brief_date"] = today
    st["busy"] = False
    state.save("state", st)


if __name__ == "__main__":
    main()
