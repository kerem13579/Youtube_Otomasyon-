"""Idea generation, with the channel's own ranking rules baked in."""
from __future__ import annotations

import re

from . import llm, state, youtube

CONCEPT_SYSTEM = """You generate concepts for a silent 30-second YouTube Shorts
channel. Every video: one recurring woman, in the same garden, transforms a
worthless everyday object into something made of concrete. No speech, no music,
only the real sounds of the work.

WHAT THE CHANNEL'S OWN 25-VIDEO DATASET PROVES (this is not theory):

1. Scale and water beat everything. A kiddie pool made into a koi pond took
   644,006 views and an umbrella made into a fountain 95,442. Coated garments
   and accessories land at 18,000-29,000. From-scratch builds and small
   accessories land at 2,600-5,100. So rank candidate ideas in this order:
     TIER 1  a large, instantly recognisable piece of household junk that ends
             up holding WATER (pond, fountain, bird bath, basin, trough)
     TIER 2  a recognisable worn object that becomes stone and keeps its
             detail (seams, rivets, stitching, treads still readable)
     TIER 3  anything built from scratch  <- almost never worth making

2. Retention is the whole game. Across the channel, the share of viewers who
   keep watching correlates with views at r=+0.73; thumbnail click-through at
   only r=+0.14. Every idea must survive the first three seconds.

3. Three traits every strong concept has:
     - a cheap or worthless input (the value gap is the story)
     - a hard, irreversible-looking middle (dipping, burying, pouring, casting)
       so the viewer thinks "she just ruined that"
     - a finished object a real person would actually put in a garden
   An idea missing the middle one will be boring no matter how well it is shot.

4. The payoff goes at the END. The opening shows the most confusing-but-
   compelling moment, never the prettiest one and never the result.

RULES YOU MUST NOT BREAK:
- Never propose an object already used by the channel, and never propose a
  different object that reaches the SAME payoff as a published video (another
  cement-dipped garment, another small succulent planter, another fountain).
- Never involve a real brand, company, logo or trademark.
- The result must be physically castable from the object, at a size that fits
  in a garden - not architecture.
"""

CONCEPT_USER = """Already published on this channel - objects and payoffs that
are now off limits:

{used}

Recent titles, so you can see what has been done:
{titles}

Generate exactly {n} NEW concepts. Aim for at least two TIER 1 (large household
object -> water feature) unless the off-limits list makes that impossible.

Return a JSON array of {n} objects, each with:
  "object_singular"  lowercase, e.g. "shopping trolley"
  "object_plural"    lowercase, e.g. "shopping trolleys"
  "result"           the finished piece in 2-5 words, e.g. "stone garden bench"
  "result_category"  one of: planter, water_feature, statue, furniture, bowl
  "tier"             1, 2 or 3
  "hook"             one sentence describing the first two seconds - the
                     apparent-destruction moment, done with hands or a whole
                     container, no craft tools
  "why"              one sentence on why this will hold viewers, referencing
                     the data above
  "tr"               the whole idea in one short Turkish sentence for the
                     channel owner to read on his phone
"""


def used_objects(uploads: list[dict]) -> list[str]:
    """Pull the object out of each published title, generously."""
    stop = {"old", "the", "that", "this", "your", "into", "them", "turn", "throw",
            "away", "dont", "don't", "toss", "concrete", "cement", "diy", "garden",
            "and", "with", "from", "for", "you", "what", "why", "how", "built",
            "poured", "turned", "result", "never", "seen", "believe", "their"}
    found = []
    for v in uploads:
        title = re.sub(r"[#@][\w-]+", " ", v["title"])
        title = re.sub(r"[^\w\s']", " ", title).lower()
        words = [w for w in title.split() if w not in stop and len(w) > 2]
        if words:
            found.append(" ".join(words[:4]))
    return found


def generate(n: int = 5, extra_instruction: str = "") -> list[dict]:
    uploads = youtube.my_uploads(limit=50)
    history = state.load("history")

    used = used_objects(uploads)
    # objects this bot proposed before, so a regenerate really is different
    used += [v.get("object") for v in history.get("videos", []) if v.get("object")]
    used += [i.get("object_singular") for i in state.load("state").get("rejected", [])
             if isinstance(i, dict)]

    titles = "\n".join(f"- {v['title']}" for v in uploads[:25]) or "(none yet)"
    user = CONCEPT_USER.format(
        used="\n".join(f"- {u}" for u in dict.fromkeys(filter(None, used))) or "(none yet)",
        titles=titles, n=n)
    if extra_instruction:
        user += f"\n\nAdditional instruction from the channel owner:\n{extra_instruction}\n"

    ideas = llm.ask_json(CONCEPT_SYSTEM, user, max_tokens=4000, temperature=1.0)
    if isinstance(ideas, dict):
        ideas = ideas.get("concepts") or ideas.get("ideas") or []
    cleaned = []
    for idea in ideas[:n]:
        if not isinstance(idea, dict) or not idea.get("object_singular"):
            continue
        idea.setdefault("result_category", "planter")
        idea.setdefault("tier", 2)
        cleaned.append(idea)
    if not cleaned:
        raise RuntimeError("Idea generation returned nothing usable")
    return cleaned


def format_for_telegram(ideas: list[dict], header: str = "") -> str:
    tier_badge = {1: "🥇 TIER 1", 2: "🥈 TIER 2", 3: "🥉 TIER 3"}
    lines = [header] if header else []
    lines.append("<b>Bugünün 5 fikri</b>\n")
    for i, idea in enumerate(ideas, 1):
        badge = tier_badge.get(int(idea.get("tier", 2)), "🥈 TIER 2")
        lines.append(
            f"<b>{i}. {idea['object_singular']} → {idea.get('result', '?')}</b>  {badge}\n"
            f"{idea.get('tr', '')}\n"
            f"<i>Açılış:</i> {idea.get('hook', '')}\n"
        )
    lines.append("Bir numaraya bas, gerisi otomatik. 🔄 ile 5 yeni fikir gelir.")
    return "\n".join(lines)
