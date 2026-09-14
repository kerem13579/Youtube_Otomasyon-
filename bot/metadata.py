"""Title / description / tag construction with enforced rotation.

The channel's failure mode was repetition: the same title shell on every
upload, and a duplicate title that cost 28,256 -> 1,506 views. Everything
here exists to make a repeat structurally impossible.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from .config import DATA, cfg
from . import state

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⬀-⯿️]"
)


def _load(name: str) -> dict:
    with (DATA / name).open(encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------- titles

def recent_title_usage(history: dict, n: int) -> list[dict]:
    return history.get("videos", [])[-n:]


def pick_title_pattern(history: dict) -> dict:
    """Choose a pattern that respects both cooldowns, newest-averse."""
    book = _load("title_patterns.json")
    patterns: list[dict] = book["patterns"]

    recent = recent_title_usage(history, cfg.title_pattern_cooldown)
    used_ids = {v.get("title_pattern") for v in recent}
    recent_fams = [v.get("title_family")
                   for v in recent_title_usage(history, cfg.title_family_cooldown)]

    pool = [p for p in patterns
            if p["id"] not in used_ids and p["family"] not in recent_fams]
    if not pool:  # cooldowns collided - relax the family rule first
        pool = [p for p in patterns if p["id"] not in used_ids]
    if not pool:  # everything used: start the cycle again
        pool = patterns

    # The proven A1 shell still carries the channel's two biggest videos, so
    # give it a mild edge whenever it is legal to use, without letting it
    # dominate the rotation.
    weights = [3 if p.get("proven") else 1 for p in pool]
    return random.choices(pool, weights=weights, k=1)[0]


_LOWER_WORDS = {"a", "an", "and", "the", "of", "in", "on", "to", "with"}


def title_case(phrase: str) -> str:
    """'watering can' -> 'Watering Can'. The templates are Title Case, so a
    lowercase object substituted into one looks like a typo."""
    words = phrase.split()
    out = []
    for i, w in enumerate(words):
        if i and w.lower() in _LOWER_WORDS:
            out.append(w.lower())
        elif w[:1].isupper() and w[1:] != w[1:].lower():
            out.append(w)          # already styled (e.g. "IKEA-style") - leave it
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def render_title(pattern: dict, obj_singular: str, obj_plural: str,
                 category: str) -> str:
    title = (pattern["template"]
             .replace("{SINGULAR}", title_case(obj_singular))
             .replace("{PLURAL}", title_case(obj_plural))
             .replace("{CATEGORY}", title_case(category)))
    return title.strip()


def validate_title(title: str, result_words: list[str],
                   allow: tuple[str, ...] = ()) -> list[str]:
    """Return a list of rule violations. Empty list means the title ships.

    `allow` carries the broad result category the pattern deliberately uses
    (the channel's 95-scoring title is "Old Shoes to Concrete Planters" - a
    broad category is fine, the SPECIFIC payoff is what must stay hidden).
    """
    problems = []
    if "|" in title:
        problems.append("contains a pipe character")
    if len(EMOJI_RE.findall(title)) > 1:
        problems.append("more than one emoji")
    if "#" in title:
        problems.append("hashtag in title")
    if len(title) > 90:
        problems.append(f"too long ({len(title)} chars)")
    if len(title) < 30:
        problems.append(f"too short ({len(title)} chars)")
    words = [w for w in re.findall(r"[A-Za-z]{4,}", title)]
    if words and sum(1 for w in words if w.isupper()) >= 2:
        problems.append("ALL CAPS words")
    low = title.lower()
    allowed = {a.strip().lower() for a in allow if a}
    allowed |= {a.rstrip("s") for a in list(allowed)}
    for rw in result_words:
        rw = rw.strip().lower()
        if not rw or len(rw) <= 3:
            continue
        if rw in allowed or rw.rstrip("s") in allowed:
            continue
        if rw in low:
            problems.append(f"names the result ('{rw}')")
    return problems


# ----------------------------------------------------------- descriptions

def build_description(history: dict, obj: str, result_category: str,
                      build_detail: str, sounds: str) -> tuple[str, str, str]:
    """Return (description, pattern_id, question).

    Shape is fixed because it is what the algorithm and the search snippet
    need; every sentence inside it rotates.
    """
    book = _load("desc_patterns.json")
    recent = {v.get("desc_pattern")
              for v in recent_title_usage(history, cfg.desc_pattern_cooldown)}
    pool = [p for p in book["patterns"] if p["id"] not in recent] or book["patterns"]
    pat = random.choice(pool)

    recent_q = {v.get("desc_question")
                for v in recent_title_usage(history, 5)}
    questions = [q for q in book["questions"] if q not in recent_q] or book["questions"]
    question = random.choice(questions)

    opener = (pat["opener"]
              .replace("{OBJ}", obj)
              .replace("{RESULT}", result_category))
    genre = random.choice(book["genre_lines"]).replace("{SOUNDS}", sounds)
    subscribe = random.choice(book["subscribe_lines"])
    hashtags = " ".join(random.choice(book["hashtag_sets"]))

    description = "\n\n".join([
        opener,
        build_detail.strip(),
        genre,
        question,
        subscribe,
        hashtags,
    ])
    return description, pat["id"], question


# ------------------------------------------------------------------ tags

def build_tags(result_family: str = "planter", limit: int = 480) -> list[str]:
    """Fill to ~480 chars from the verified pool. Never touches the blacklist."""
    vocab = _load("tag_vocabulary.json")
    blacklist = {t.lower() for t in vocab["blacklist"]}

    ordered: list[str] = []
    ordered += vocab["core"]
    ordered += vocab["result_families"].get(result_family, [])
    ordered += vocab["craft_upcycle"]
    ordered += vocab["genre"]

    chosen: list[str] = []
    length = 0
    for tag in ordered:
        if tag.lower() in blacklist or tag in chosen:
            continue
        add = len(tag) + (2 if chosen else 0)
        if length + add > limit:
            continue
        chosen.append(tag)
        length += add
    return chosen


def tags_length(tags: list[str]) -> int:
    return len(", ".join(tags))


# ---------------------------------------------------------------- record

def record_upload(history: dict, entry: dict[str, Any]) -> None:
    history.setdefault("videos", []).append(entry)
    state.save("history", history)
