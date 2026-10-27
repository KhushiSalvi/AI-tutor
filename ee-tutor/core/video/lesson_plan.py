"""Turn a query into a lesson plan (list of scenes) for the video renderer.

Grounding rules are identical in spirit to the text tutor: every scene's narration and
bullets must come from the retrieved book sources, not general knowledge. This module
only decides HOW MUCH content fits in the target video length; the actual generation
prompt reuses the same "book only" discipline as core.tutor.
"""
import json
import re

WORDS_PER_SECOND = 2.5          # measured: sentence-by-sentence pyttsx3 synthesis averages ~2.9-3.3 wps
                                 # conservative since technical narration reads a bit slower
import os
TARGET_SECONDS = int(os.environ.get("VIDEO_SECONDS", "30"))   # default 30s; set VIDEO_SECONDS=60 for longer
MAX_SECONDS = int(TARGET_SECONDS * 1.3)                       # hard cap before we force a trim
MIN_SCENES = 3
MAX_SCENES = max(3, round(TARGET_SECONDS / 9))                # ~9-10s per scene

VIDEO_SYSTEM = """You are creating a short narrated video script for an electrical engineering
student, using ONLY the numbered SOURCES provided. The same grounding rules as normal answers
apply: every scene's narration and bullets must be traceable to the sources; never fill gaps
with outside knowledge; if the sources only cover part of the topic, cover only that part.

The WHOLE video must be about {total_s} seconds, so keep it tight: one idea per scene.
Plan the video as {min_s} to {max_s} short scenes, each roughly {sec_per_scene} seconds of
spoken narration (about {words_per_scene} words). Order scenes so each builds on the last:
start with what the thing is, then how it works, then a key formula or example if the sources
give one, then a brief takeaway. Keep narration conversational and clear, as if explaining to
a first-year student out loud -- short sentences, no dense jargon without a quick definition.

Each scene also needs a "visual" -- a simple animated diagram, chosen from exactly these
four types, picked for whichever best fits that scene's content:
- "title_bullets": title plus 1-3 short on-screen phrases appearing one by one. The safe
  default for a definition, a list of properties, or a summary/takeaway.
- "formula_build": a single equation that builds up term by term. Use only when the scene's
  main point IS a formula from the sources.
- "flow": a left-to-right chain of 3-5 short labeled stages with a moving indicator, for
  anything sequential or process-like (pipeline stages, signal/current/data flow, steps of
  an algorithm, stages of operation).
- "compare": two labeled columns side by side, each with 2-3 short points, for anything
  contrastive (A vs B, two regions/modes/types).

Return ONLY a JSON object (no markdown fences):
"found": true if the sources cover this topic well enough for a video, else false
"video_title": short title, max 8 words
"scenes": list of objects, each with:
    "title": short scene heading, max 6 words
    "narration": the spoken script for this scene, {words_per_scene} words or fewer
    "citation": one source reference like "source_id p.NN" for this scene's main source
    "visual": one of:
        {{"type": "title_bullets", "bullets": ["...", "..."]}}
        {{"type": "formula_build", "formula": "plain ASCII equation from the sources", "formula_where": "one line defining the symbols"}}
        {{"type": "flow", "nodes": ["stage 1", "stage 2", "stage 3"]}}
        {{"type": "compare", "left": {{"label": "...", "points": ["...", "..."]}}, "right": {{"label": "...", "points": ["...", "..."]}}}}
If "found" is false, still return "video_title" and an empty "scenes" list, and add
"reason": a one-sentence explanation of what's missing from the sources."""


def build_video_prompt(query):
    sec_per_scene = max(6, round(TARGET_SECONDS / MIN_SCENES))
    words_per_scene = int(sec_per_scene * WORDS_PER_SECOND)
    return VIDEO_SYSTEM.format(
        total_s=TARGET_SECONDS, min_s=MIN_SCENES, max_s=MAX_SCENES,
        sec_per_scene=sec_per_scene, words_per_scene=words_per_scene,
    )


def estimate_seconds(scenes):
    total = 0
    for s in scenes:
        words = len((s.get("narration", "")).split())
        total += words / WORDS_PER_SECOND
    return total


def trim_to_budget(scenes, max_seconds=MAX_SECONDS, min_scenes=MIN_SCENES):
    """Drop the lowest-value scenes first (later scenes = more optional, in this simple
    ordering-based heuristic) until we're under budget or hit the floor of min_scenes."""
    scenes = list(scenes)
    while len(scenes) > min_scenes and estimate_seconds(scenes) > max_seconds:
        scenes.pop(-2)  # keep the intro (first) and the takeaway (last); trim the middle
    return scenes


def sanitize_scene(sc):
    """Defensive validation of one LLM-produced scene before it reaches the renderer.
    Falls back to a safe title_bullets visual if the chosen type's required fields are
    missing or malformed, so a bad LLM response degrades to a plain scene instead of a
    broken or empty animation."""
    visual = sc.get("visual") or {}
    vtype = visual.get("type")

    if vtype == "flow":
        nodes = [str(x) for x in visual.get("nodes", []) if str(x).strip()]
        if len(nodes) >= 2:
            sc["visual"] = {"type": "flow", "nodes": nodes[:6]}
            return sc
    elif vtype == "formula_build":
        formula = str(visual.get("formula", "")).strip()
        if formula:
            sc["visual"] = {"type": "formula_build", "formula": formula,
                             "formula_where": str(visual.get("formula_where", ""))}
            return sc
    elif vtype == "compare":
        left, right = visual.get("left") or {}, visual.get("right") or {}
        if left.get("points") and right.get("points"):
            sc["visual"] = {
                "type": "compare",
                "left": {"label": str(left.get("label", "")), "points": [str(x) for x in left["points"]][:3]},
                "right": {"label": str(right.get("label", "")), "points": [str(x) for x in right["points"]][:3]},
            }
            return sc

    # default / fallback: title_bullets, using whatever bullets exist or a generic one
    bullets = [str(x) for x in (visual.get("bullets") or sc.get("bullets") or [])][:3]
    sc["visual"] = {"type": "title_bullets", "bullets": bullets or [sc.get("title", "")]}
    return sc


def sanitize_scenes(scenes):
    return [sanitize_scene(dict(sc)) for sc in scenes]
