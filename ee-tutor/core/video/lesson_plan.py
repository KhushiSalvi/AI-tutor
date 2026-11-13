"""Turn a query into a lesson plan (list of scenes) for the video renderer.

Grounding rules are identical in spirit to the text tutor: every scene's narration and
bullets must come from the retrieved book sources, not general knowledge. This module
only decides HOW MUCH content fits in the target video length; the actual generation
prompt reuses the same "book only" discipline as core.tutor.
"""
import json
import os
import re

WORDS_PER_SECOND = 2.5           # measured: sentence-by-sentence pyttsx3 ~2.9-3.3 wps
                                  # conservative because technical narration is slower

# Default 150s (2.5 min); hard cap 270s (4.5 min). Set VIDEO_SECONDS env var to override.
TARGET_SECONDS = min(int(os.environ.get("VIDEO_SECONDS", "150")), 270)
MAX_SECONDS    = int(TARGET_SECONDS * 1.2)         # hard cap before we force a trim
MIN_SCENES     = 5
MAX_SCENES     = max(MIN_SCENES, round(TARGET_SECONDS / 22))  # ~20-25s per scene

VIDEO_SYSTEM = """You are creating a 2.5-to-4-minute narrated video lesson for a college EE/CS
student, using ONLY the numbered SOURCES provided. The same grounding rules as normal answers
apply: every scene's narration and bullets must be traceable to the sources; never fill gaps
with outside knowledge; if the sources only cover part of the topic, cover only that part.

The WHOLE video must be about {total_s} seconds ({total_min:.1f} minutes).
Plan {min_s} to {max_s} scenes, each roughly {sec_per_scene} seconds of spoken narration
(about {words_per_scene} words). Structure the video as a mini-lecture:
  Scene 1:   "What is it?" -- hook + one-sentence definition
  Scenes 2-3: "How does it work?" -- mechanism, key equations, physical intuition
  Scenes 4-5: "Example / Application" -- a concrete worked example or circuit from the sources
  Last scene: "Key Takeaway" -- one memorable summary + exam tip if sources give one

Keep narration conversational. Short sentences. Define every symbol on first use.

Each scene needs a "visual" -- choose the type that BEST matches the content:
- "title_bullets":    title + 1-3 bullet phrases. Safe default for definitions/summaries.
- "formula_build":    equation built term-by-term. Only for scenes whose main point IS a formula.
- "flow":             left-to-right 3-5 stages + animated particle. For any sequential process,
                      pipeline, signal path, current path, or algorithm steps.
- "compare":          two side-by-side columns. For A-vs-B, two operating regions, two modes.
- "circuit_flow":     schematic component chain (R, C, L, diode, transistor, op-amp blocks)
                      with animated current dot. Use for circuits and signal chains.
- "waveform_plot":    animated SVG graph. Choose shape from: sine, rc_charge, square, sawtooth.
                      Use for time-domain waveforms, transient response, signal shapes.
- "pipeline_timing":  CPU pipeline grid (stages x cycles). Use ONLY for processor pipeline topics.
- "logic_truth":      gate symbol + computed truth table. Use for logic gates and boolean algebra.
- "block_diagram":    labeled boxes with arrow edges + optional highlight pulse. Use for
                      architecture diagrams, system overviews, subsystem relationships.

Return ONLY a JSON object (no markdown fences):
"found": true if the sources cover this topic well enough for a 2-4 min video, else false
"video_title": short title, max 8 words
"scenes": list of objects, each with:
    "title": short scene heading, max 6 words
    "narration": spoken script, {words_per_scene} words or fewer
    "citation": one source ref like "source_id p.NN"
    "visual": exactly one of:
        {{"type": "title_bullets", "bullets": ["...", "..."]}}
        {{"type": "formula_build", "formula": "ASCII eq", "formula_where": "symbol definitions"}}
        {{"type": "flow", "nodes": ["stage 1", "stage 2", "stage 3"]}}
        {{"type": "compare", "left": {{"label": "...", "points": ["..."]}}, "right": {{"label": "...", "points": ["..."]}}}}
        {{"type": "circuit_flow", "components": ["R1 10ohm", "C1 10uF"], "label_in": "Vin", "label_out": "Vout"}}
        {{"type": "waveform_plot", "shape": "sine", "x_label": "Time (s)", "y_label": "V(t)", "highlight_x": 0.5}}
        {{"type": "pipeline_timing", "stages": ["IF","ID","EX","MEM","WB"], "cycles": 8, "instructions": 3}}
        {{"type": "logic_truth", "gate": "AND", "inputs": ["A","B"], "output": "Y"}}
        {{"type": "block_diagram", "blocks": [{{"id":"cpu","label":"CPU"}},{{"id":"mem","label":"Memory"}}], "edges": [{{"from":"cpu","to":"mem","label":"bus"}}], "highlight": "cpu"}}
If "found" is false, still return "video_title" and an empty "scenes" list, and add
"reason": a one-sentence explanation of what's missing from the sources."""


def build_video_prompt(query):
    sec_per_scene  = max(10, round(TARGET_SECONDS / MAX_SCENES))
    words_per_scene = int(sec_per_scene * WORDS_PER_SECOND)
    return VIDEO_SYSTEM.format(
        total_s=TARGET_SECONDS,
        total_min=TARGET_SECONDS / 60,
        min_s=MIN_SCENES,
        max_s=MAX_SCENES,
        sec_per_scene=sec_per_scene,
        words_per_scene=words_per_scene,
    )


def estimate_seconds(scenes):
    total = 0
    for s in scenes:
        words = len((s.get("narration", "")).split())
        total += words / WORDS_PER_SECOND
    return total


def trim_to_budget(scenes, max_seconds=MAX_SECONDS, min_scenes=MIN_SCENES):
    """Drop the lowest-value scenes first (later middle scenes = more optional) until
    we're under budget or hit the floor of min_scenes."""
    scenes = list(scenes)
    while len(scenes) > min_scenes and estimate_seconds(scenes) > max_seconds:
        scenes.pop(-2)   # keep the intro (first) and the takeaway (last); trim the middle
    return scenes


# ---------------------------------------------------------------------------
# Sanitize helpers for the 5 new template types
# ---------------------------------------------------------------------------

def _sanitize_circuit_flow(visual):
    comps = [str(x) for x in (visual.get("components") or []) if str(x).strip()]
    if len(comps) >= 2:
        return {
            "type": "circuit_flow",
            "components": comps[:5],
            "label_in":  str(visual.get("label_in", "Vin")),
            "label_out": str(visual.get("label_out", "Vout")),
        }
    return None


def _sanitize_waveform_plot(visual):
    VALID_SHAPES = {"sine", "rc_charge", "square", "sawtooth"}
    shape = str(visual.get("shape", "sine")).lower()
    if shape not in VALID_SHAPES:
        shape = "sine"
    hx = visual.get("highlight_x", -1)
    try:
        hx = float(hx)
    except (TypeError, ValueError):
        hx = -1
    return {
        "type":        "waveform_plot",
        "shape":       shape,
        "x_label":     str(visual.get("x_label", "Time"))[:20],
        "y_label":     str(visual.get("y_label", "Amplitude"))[:20],
        "highlight_x": hx,
    }


def _sanitize_pipeline_timing(visual):
    stages = [str(s) for s in (visual.get("stages") or ["IF","ID","EX","MEM","WB"]) if str(s).strip()]
    if not stages:
        return None
    try:
        cycles = min(int(visual.get("cycles") or 8), 9)
    except (TypeError, ValueError):
        cycles = 8
    try:
        instructions = min(int(visual.get("instructions") or 3), 4)
    except (TypeError, ValueError):
        instructions = 3
    return {
        "type":         "pipeline_timing",
        "stages":       stages[:6],
        "cycles":       cycles,
        "instructions": instructions,
    }


def _sanitize_logic_truth(visual):
    VALID_GATES = {"AND", "OR", "NOT", "NAND", "NOR", "XOR"}
    gate = str(visual.get("gate", "AND")).upper()
    if gate not in VALID_GATES:
        gate = "AND"
    inputs = [str(x) for x in (visual.get("inputs") or ["A", "B"])][:2]
    return {
        "type":   "logic_truth",
        "gate":   gate,
        "inputs": inputs,
        "output": str(visual.get("output", "Y"))[:4],
    }


def _sanitize_block_diagram(visual):
    blocks = []
    for b in (visual.get("blocks") or []):
        if isinstance(b, dict) and b.get("id") and b.get("label"):
            blocks.append({"id": str(b["id"]), "label": str(b["label"])[:30]})
    if not blocks:
        return None
    edges = []
    for e in (visual.get("edges") or []):
        if isinstance(e, dict) and e.get("from") and e.get("to"):
            edges.append({
                "from":  str(e["from"]),
                "to":    str(e["to"]),
                "label": str(e.get("label", ""))[:20],
            })
    return {
        "type":      "block_diagram",
        "blocks":    blocks[:6],
        "edges":     edges[:8],
        "highlight": str(visual.get("highlight", "")),
    }


def sanitize_scene(sc):
    """Defensive validation of one LLM-produced scene before it reaches the renderer.
    Falls back to a safe title_bullets visual if the chosen type's required fields are
    missing or malformed, so a bad LLM response degrades to a plain scene instead of a
    broken or empty animation.
    """
    visual = sc.get("visual") or {}
    vtype  = visual.get("type")

    # --- original 4 types ---
    if vtype == "flow":
        nodes = [str(x) for x in visual.get("nodes", []) if str(x).strip()]
        if len(nodes) >= 2:
            sc["visual"] = {"type": "flow", "nodes": nodes[:6]}
            return sc
    elif vtype == "formula_build":
        formula = str(visual.get("formula", "")).strip()
        if formula:
            sc["visual"] = {
                "type": "formula_build",
                "formula": formula,
                "formula_where": str(visual.get("formula_where", "")),
            }
            return sc
    elif vtype == "compare":
        left, right = visual.get("left") or {}, visual.get("right") or {}
        if left.get("points") and right.get("points"):
            sc["visual"] = {
                "type": "compare",
                "left":  {"label": str(left.get("label", "")),  "points": [str(x) for x in left["points"]][:3]},
                "right": {"label": str(right.get("label", "")), "points": [str(x) for x in right["points"]][:3]},
            }
            return sc

    # --- 5 new types ---
    elif vtype == "circuit_flow":
        result = _sanitize_circuit_flow(visual)
        if result:
            sc["visual"] = result
            return sc
    elif vtype == "waveform_plot":
        sc["visual"] = _sanitize_waveform_plot(visual)
        return sc
    elif vtype == "pipeline_timing":
        result = _sanitize_pipeline_timing(visual)
        if result:
            sc["visual"] = result
            return sc
    elif vtype == "logic_truth":
        sc["visual"] = _sanitize_logic_truth(visual)
        return sc
    elif vtype == "block_diagram":
        result = _sanitize_block_diagram(visual)
        if result:
            sc["visual"] = result
            return sc

    # default / fallback: title_bullets
    bullets = [str(x) for x in (visual.get("bullets") or sc.get("bullets") or [])][:3]
    sc["visual"] = {"type": "title_bullets", "bullets": bullets or [sc.get("title", "")]}
    return sc


def sanitize_scenes(scenes):
    return [sanitize_scene(dict(sc)) for sc in scenes]
