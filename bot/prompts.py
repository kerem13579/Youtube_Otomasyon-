"""Writes the Seedance JSON prompt and the metadata that ships with it.

The craftsmanship rules in PROMPT_SYSTEM are the fix for the specific
complaint that the finished pieces had started looking generic: a coated
object with no surviving detail and a flat paint job reads as a product
render, and the channel's low-retention uploads all look like that.
"""
from __future__ import annotations

import json

from . import llm

PROMPT_SYSTEM = """You write JSON generation prompts for a 30-second, 9:16,
single-shot AI video. One recurring woman, locked to a reference image,
transforms a worthless object into concrete in the same garden. Silent apart
from the real sounds of the work.

## The five-beat spine - never change its shape

| Beat | Time | Speed | Job |
|---|---|---|---|
| 1 | 0-6s   | REAL TIME          | Hook: the single most arresting physical action |
| 2 | 6-12s  | REAL TIME          | Second detail beat, proves the technique is real |
| 3 | 12-22s | FAST TIME-LAPSE    | The whole middle of the build races past |
| 4 | 22-27s | REAL TIME          | Finishing touch, speed settles |
| 5 | 27-30s | REAL TIME          | The reveal - maker and finished piece in frame |

slow, slow, fast, slow, slow. Real time first, or the material never behaves
and the whole thing reads as fake.

## Beat 1 is the whole video

Open on APPARENT DESTRUCTION: an intact, recognisable, appealing object being
submerged, buried, smeared or coated. Three tests it must pass:
- Freeze at 2 seconds: does that single frame make a stranger ask a question?
- NO craft tools in the first two seconds. No trowel, brush, ladle, spatula,
  scoop. The first action uses her hands or a whole container - dumping,
  plunging, tipping, tearing. Volume and speed read as destruction; a tool
  reads as tutorial and viewers leave.
- Show the object IN USE for half a second first if it can be - the hat on her
  head, the boots on her feet. That half second makes it hers and the loss real.
Never show the finished result, not even a flash. Open mid-action.

## Craftsmanship - the part that has been failing

A concrete transformation is only impressive if the viewer can see that a real
object is underneath. Four requirements, all mandatory:

1. `critical_detail` must name the SPECIFIC surviving feature of THIS object
   and say why it matters - the stitching and eyelets of a boot, the rivets
   and seam of a watering can, the tread blocks of a tire, the wicker weave of
   a basket. "Coated evenly" is not a critical detail; it is the failure.
2. The finished piece must have ONE signature touch that no mass-produced
   garden ornament would have: a hand-painted motif, a deliberate two-tone
   edge, moss pressed into a crevice, a burnished rim, an inlaid pebble line.
   Name it concretely. Never "painted white and planted".
3. Ask for FLAWS explicitly: uneven paint, visible trowel ridges, a thumbprint
   set in the rim, drips down one side, crumbs of dry mix on the grass.
   Without this the render looks like a product photo and the craft reads fake.
4. State the finished height against her body. Models inflate small crafts
   into architecture otherwise.

## Other load-bearing rules

- `location` says "the same garden throughout" and "NOT an indoor studio".
  Models default hard to grey seamless backdrops.
- `dialogue` says "NO speech, NO talking, NO lip movement, nobody addresses
  the camera."
- `sound` goes INSIDE each beat, written as physical events - "the wet suck
  and scrape of the trowel pulling cement out of the bucket" - never a global
  "nature sounds" line, which produces birdsong over silent work.
- `shot` changes between beats. Five identical framings reads as a stiff video.
- `action` is observable physical behaviour, never intent. Not "she coats it
  thoroughly" but "she presses cement into the denim with her palms until no
  denim colour shows".
- Identity lock: face, hair, skin tone, body type and the exact outfit from
  the reference image, for the entire 30 seconds, no wardrobe change, no face
  drift between cuts.
- Never write a real trademark, company, logo or branded backdrop.
- `negative_prompt` is one flat comma-separated string: start with the
  standing list, then ADD entries for what THIS build could collapse into.

## Output

Return one JSON object with exactly these top-level keys:
  audio_requirement, reference_images, subject_of_build, global_style, beats,
  realism_first, quality_directives, negative_prompt
`beats` is an array of 5 objects with t, speed, shot, action, sound.
`subject_of_build` has what, method, critical_detail, final_look.
`realism_first` has materials, weight_and_physics, imperfection, scale.
`quality_directives` has timelapse_execution, hands, face, continuity,
framing, no_text.
"""

METADATA_SYSTEM = """You write the YouTube metadata that ships with a silent
30-second concrete-transformation Short on a US channel.

Hard rules:
- The description's first ~125 characters are the only part shown in search.
  Lead with the main keyword and the value promise, as one natural sentence.
- The build detail is 2-3 sentences: what it was made from, the odd technique,
  what it is for. Concrete nouns, no adjectives-for-adjectives' sake.
- Name the three actual sounds of THIS build, not the category. "the wet
  cement, the trowel and the birds", not "satisfying sounds".
- Never a timestamp block. These are 30-second Shorts.
Return JSON with keys: build_detail, sounds, result_category, result_words.
`result_words` is a list of 2-4 words naming the finished piece - the title
checker uses them to make sure the title never gives the ending away.
"""


def write_video_prompt(idea: dict, avatar_note: str,
                       extra: str = "") -> dict:
    user = f"""Concept:
- object: {idea['object_singular']}
- finished piece: {idea.get('result')}
- opening hook the owner approved: {idea.get('hook')}
- why it should hold viewers: {idea.get('why')}

Reference image 1 is the woman. {avatar_note}

Write the JSON prompt.{(' ' + extra) if extra else ''}"""
    payload = llm.ask_json(PROMPT_SYSTEM, user, max_tokens=8000,
                                  temperature=1.0)
    if not isinstance(payload, dict) or "beats" not in payload:
        raise RuntimeError("Prompt writer returned an unexpected shape")
    return payload


def write_metadata_parts(idea: dict, video_prompt: dict) -> dict:
    user = f"""Object: {idea['object_singular']}
Finished piece: {idea.get('result')}
Method, from the generation prompt: {json.dumps(video_prompt.get('subject_of_build', {}))[:1200]}

Write the metadata parts."""
    parts = llm.ask_json(METADATA_SYSTEM, user, max_tokens=2000,
                                temperature=0.8)
    parts.setdefault("result_category", idea.get("result_category", "planter"))
    parts.setdefault("sounds", "the wet cement, the trowel and the birds")
    parts.setdefault("result_words", [idea.get("result", "")])
    return parts


def flatten_for_wavespeed(video_prompt: dict) -> str:
    """WaveSpeed takes a text prompt; the JSON goes in as text, which is what
    the video models were trained to follow for this format."""
    return json.dumps(video_prompt, ensure_ascii=False, indent=1)
