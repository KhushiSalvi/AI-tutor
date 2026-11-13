"""Agentic video generator — Gemini native function calling.

Flow:
  search_textbook → set_style → add_scene × N →
  [per scene: select_background → build_animation → compute_data? →
   write_narration → synthesize_narration → render_scene → preview_scene] →
  merge_scenes → finish_video

All tool calls are logged to data/videos/<job_id>/trace.json.
Progress is written to data/videos/<job_id>/progress.json (read by VideoCard).
"""
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── constants ─────────────────────────────────────────────────────────────────

MAX_TOOL_CALLS  = 40
MAX_RETRIES     = 2
TIMEOUT_SECONDS = 300   # 5 min
FPS             = 12
TAIL_PAD        = 0.5

VIDEO_DIR = Path("data/videos")

AGENT_SYSTEM = """\
You are a video director for an electrical engineering tutor. Your job:
1. CALL search_textbook FIRST — all facts, equations and numbers must come from the sources.
2. CALL set_style to lock a consistent visual style for the whole video.
3. CALL add_scene 4–7 times to plan the story arc:
     hook → concept/structure → mechanism/working → graph or calculation → application → recap
   Choose scene TYPES that match the topic:
     • Device topics (MOSFET, diode, BJT) → device_cross_section + circuit_diagram + graph
     • Signal/waveform topics → graph + equation_steps + circuit_diagram
     • Algorithm/process topics → flow + bullets + split_compare
     • Comparison topics → split_compare + bullets
4. For each scene IN ORDER: select_background, build_animation, compute_data (for ANY number
   shown on screen), write_narration, synthesize_narration, render_scene, preview_scene.
   Fix what you see in the preview before moving on.
5. When ALL scenes are good: merge_scenes, then finish_video.

Rules:
- Facts come ONLY from search_textbook results. Mark anything else "general knowledge".
- NEVER invent numbers — call compute_data for every value shown in a graph or equation.
- Narration ≈ 2.5 words/second of scene length. Keep it conversational and clear.
- If a scene fails twice, call build_animation with type=bullets as a safe fallback.
- Max 40 tool calls total. If you're close to the limit, merge and finish immediately.
"""

BACKGROUND_CHOICES = {
    "hook":               "gradient",
    "concept_diagram":    "blueprint",
    "device_cross_section": "blueprint",
    "working_animation":  "grid",
    "graph":              "grid",
    "calculation":        "blueprint",
    "comparison":         "gradient",
    "application":        "dots",
    "recap":              "gradient",
    "bullets":            "gradient",
}


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class SceneData:
    id: int
    scene_type: str = "bullets"
    title: str = ""
    purpose: str = ""
    background_spec: dict = field(default_factory=dict)
    animation_spec: dict = field(default_factory=dict)
    narration: str = ""
    citation: str = ""
    audio_path: str = ""
    audio_duration: float = 0.0
    mp4_path: str = ""
    preview_b64: str = ""   # base64 PNG of one mid-scene frame
    retries: int = 0
    done: bool = False


@dataclass
class VideoJob:
    id: str
    query: str
    level: str = "beginner"
    style: dict = field(default_factory=dict)
    scenes: list = field(default_factory=list)   # list[SceneData]
    finished: bool = False
    final_mp4: str = ""
    error: str = ""
    tool_calls: int = 0
    trace: list = field(default_factory=list)    # [{tool, args, result, ms}]


# ── progress helpers ──────────────────────────────────────────────────────────

def _write_progress(work: Path, msg: str) -> None:
    try:
        (work / "progress.json").write_text(
            json.dumps({"detail": msg}), encoding="utf-8"
        )
    except OSError:
        pass


def _write_trace(work: Path, trace: list) -> None:
    try:
        (work / "trace.json").write_text(
            json.dumps(trace, indent=2, default=str), encoding="utf-8"
        )
    except OSError:
        pass


# ── tool implementations ──────────────────────────────────────────────────────

def _tool_search_textbook(job: VideoJob, work: Path, args: dict) -> dict:
    query = str(args.get("query", job.query))
    try:
        from core.tutor import retrieve
        sources = retrieve(query, job.level)
    except Exception as e:
        return {"error": str(e), "chunks": []}
    chunks = [
        {"n": s.get("n", i + 1), "source": s.get("source_id", ""), 
         "page": s.get("page"), "text": s.get("text", "")[:500]}
        for i, s in enumerate(sources[:6])
    ]
    return {"chunks": chunks, "count": len(chunks)}


def _tool_set_style(job: VideoJob, work: Path, args: dict) -> dict:
    job.style = {
        "palette":         str(args.get("palette", "dark_tech")),
        "primary_color":   str(args.get("primary_color", "#7aa2f7")),
        "accent_color":    str(args.get("accent_color", "#9ece6a")),
        "motion_language": str(args.get("motion_language", "smooth")),
        "mood":            str(args.get("mood", "focused")),
    }
    return {"status": "ok", "style": job.style}


def _tool_add_scene(job: VideoJob, work: Path, args: dict) -> dict:
    sc = SceneData(
        id=len(job.scenes),
        scene_type=str(args.get("type", "bullets")),
        title=str(args.get("title", f"Scene {len(job.scenes)+1}"))[:80],
        purpose=str(args.get("purpose", ""))[:200],
    )
    job.scenes.append(sc)
    return {"scene_id": sc.id, "title": sc.title, "type": sc.scene_type}


def _tool_select_background(job: VideoJob, work: Path, args: dict) -> dict:
    sid   = int(args.get("scene_id", 0))
    kind  = str(args.get("kind", "gradient"))
    query = str(args.get("query", ""))

    sc = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}

    if kind == "gradient":
        p  = job.style.get("primary_color", "#0d0f1a")
        a  = job.style.get("accent_color", "#1a1f3a")
        sc.background_spec = {"kind": "gradient", "color1": "#0d0f1a",
                              "color2": "#111827", "angle": 135}
        return {"kind": "gradient", "description": f"dark gradient ({p} → {a})"}

    if kind in ("grid", "blueprint", "dots", "pattern"):
        pat = kind if kind in ("grid", "blueprint", "dots") else "grid"
        sc.background_spec = {"kind": "pattern", "pattern": pat}
        return {"kind": "pattern", "pattern": pat, "description": f"{pat} pattern background"}

    if kind == "web_image":
        path, desc, credit = _fetch_wikimedia(query, work / "assets")
        if path:
            sc.background_spec = {"kind": "image", "path": str(path), "credit": credit}
            return {"kind": "image", "path": str(path), "description": desc, "credit": credit}
        # Fallback to blueprint
        sc.background_spec = {"kind": "pattern", "pattern": "blueprint"}
        return {"kind": "pattern", "pattern": "blueprint",
                "description": f"web image unavailable, using blueprint (searched: {query})"}

    sc.background_spec = {"kind": "gradient", "color1": "#0d0f1a", "color2": "#111827", "angle": 135}
    return {"kind": "gradient", "description": "default dark gradient"}


def _tool_build_animation(job: VideoJob, work: Path, args: dict) -> dict:
    sid   = int(args.get("scene_id", 0))
    atype = str(args.get("animation_type", "bullets"))
    spec  = args.get("spec", {})
    if not isinstance(spec, dict):
        try:
            spec = json.loads(str(spec))
        except Exception:
            spec = {}

    sc = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}

    # Validate / sanitize per type
    VALID_TYPES = {
        "circuit_diagram", "device_cross_section", "graph",
        "equation_steps", "flow", "bullets", "split_compare", "waveform",
    }
    if atype not in VALID_TYPES:
        atype = "bullets"

    sc.animation_spec = {"type": atype, **spec}
    return {"status": "ok", "scene_id": sid, "animation_type": atype,
            "spec_keys": list(spec.keys())}


def _tool_compute_data(job: VideoJob, work: Path, args: dict) -> dict:
    expression = str(args.get("expression", ""))
    variables  = args.get("variables", {})
    sweep      = args.get("sweep", {})

    if not isinstance(variables, dict):
        variables = {}

    try:
        from core.video.safe_eval import safe_eval, compute_sweep
    except ImportError:
        return {"error": "safe_eval module not available"}

    try:
        if sweep:
            var  = str(sweep.get("variable", "x"))
            start = float(sweep.get("start", 0))
            stop  = float(sweep.get("stop", 1))
            n     = min(int(sweep.get("n", 200)), 500)
            log   = bool(sweep.get("log_scale", False))
            xs, ys = compute_sweep(expression, var, start, stop, n, log)
            return {"xs": xs[:200], "ys": ys[:200], "variable": var,
                    "n_points": len(xs), "y_min": min(ys), "y_max": max(ys)}
        else:
            result = safe_eval(expression, {str(k): v for k, v in variables.items()})
            import numpy as np
            if hasattr(result, "tolist"):
                result = result.tolist()
            return {"result": result}
    except Exception as e:
        return {"error": str(e)}


def _tool_write_narration(job: VideoJob, work: Path, args: dict) -> dict:
    sid  = int(args.get("scene_id", 0))
    text = str(args.get("text", "")).strip()
    sc   = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}
    if not text:
        return {"error": "text must not be empty"}
    sc.narration = text
    word_count   = len(text.split())
    est_seconds  = round(word_count / 2.5, 1)
    return {"status": "ok", "scene_id": sid, "words": word_count,
            "estimated_duration_s": est_seconds}


def _tool_synthesize_narration(job: VideoJob, work: Path, args: dict) -> dict:
    sid   = int(args.get("scene_id", 0))
    voice = str(args.get("voice", "en-US-AriaNeural"))
    sc    = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}
    if not sc.narration:
        return {"error": "write_narration must be called before synthesize_narration"}

    wav_path = work / f"scene_{sid}_narration.wav"
    try:
        from core.video.tts import synthesize_with_cache
        synthesize_with_cache(sc.narration, wav_path, work, f"scene_{sid}", log=print)
        dur = _wav_duration(wav_path)
        sc.audio_path     = str(wav_path)
        sc.audio_duration = max(dur, 2.0)
        return {"status": "ok", "scene_id": sid, "duration_s": sc.audio_duration,
                "audio_path": str(wav_path)}
    except Exception as e:
        sc.audio_path     = ""
        sc.audio_duration = max(len(sc.narration.split()) / 2.5, 2.0)
        return {"warning": str(e), "estimated_duration_s": sc.audio_duration}


def _tool_render_scene(job: VideoJob, work: Path, args: dict) -> dict:
    sid = int(args.get("scene_id", 0))
    sc  = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}
    if sc.retries >= MAX_RETRIES:
        return {"error": f"scene {sid} already failed {MAX_RETRIES} times — use bullets fallback"}

    try:
        from core.video.scene_html import render_agent_scene_html
        from playwright.sync_api import sync_playwright

        html = render_agent_scene_html(sc.__dict__, sid + 1, len(job.scenes))
        dur  = max(sc.audio_duration, 2.0)
        wav  = Path(sc.audio_path) if sc.audio_path else _make_silent_wav(work, sid, dur)
        mp4  = work / f"scene_{sid}.mp4"

        _render_scene_to_mp4(html, dur, wav, mp4, progress=lambda m: _write_progress(work, m))
        sc.mp4_path = str(mp4)
        sc.done = True
        return {"status": "ok", "scene_id": sid, "mp4": str(mp4), "duration_s": dur}
    except Exception as e:
        sc.retries += 1
        return {"error": str(e), "retries_left": MAX_RETRIES - sc.retries}


def _tool_preview_scene(job: VideoJob, work: Path, args: dict) -> dict:
    sid = int(args.get("scene_id", 0))
    sc  = _get_scene(job, sid)
    if sc is None:
        return {"error": f"scene_id {sid} not found"}

    try:
        from core.video.scene_html import render_agent_scene_html
        from playwright.sync_api import sync_playwright

        html = render_agent_scene_html(sc.__dict__, sid + 1, len(job.scenes))
        dur  = max(sc.audio_duration, 2.0)

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page    = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_content(html)
            page.wait_for_timeout(80)
            # Seek to mid-scene
            page.evaluate(
                "(t) => { document.querySelectorAll('.anim').forEach(el => {"
                "const s=parseFloat(el.dataset.start||'0');"
                "el.style.animationDelay=(s-t)+'s';});}",
                dur * 0.5
            )
            png = page.screenshot(type="png")
            browser.close()

        sc.preview_b64 = base64.b64encode(png).decode()
        # Heuristic quality check: PNG < 15KB → probably blank
        quality = "ok" if len(png) > 15_000 else "blank_or_broken"
        return {"status": quality, "scene_id": sid,
                "preview_size_kb": round(len(png) / 1024, 1),
                "advice": "looks good" if quality == "ok" else
                          "scene appears blank — rebuild animation or select different background"}
    except Exception as e:
        return {"warning": str(e), "status": "preview_failed"}


def _tool_merge_scenes(job: VideoJob, work: Path, args: dict) -> dict:
    order      = args.get("order", list(range(len(job.scenes))))
    transition = str(args.get("transition", "none"))  # none | fade

    # Collect available clips in order
    clips = []
    for idx in order:
        sc = _get_scene(job, int(idx))
        if sc and sc.mp4_path and Path(sc.mp4_path).exists():
            clips.append(Path(sc.mp4_path))

    if not clips:
        return {"error": "no rendered scenes to merge"}

    final = VIDEO_DIR / f"{job.id}.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)

    if len(clips) == 1:
        shutil.copy2(clips[0], final)
    else:
        lst = work / "concat.txt"
        lst.write_text(
            "\n".join(f"file '{c.resolve().as_posix()}'" for c in clips),
            encoding="utf-8"
        )
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(lst),
             "-c", "copy", str(final)],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            return {"error": f"ffmpeg merge failed: {r.stderr[-400:]}"}

    job.final_mp4 = str(final)
    total_s = sum(
        _get_scene(job, int(i)).audio_duration
        for i in order
        if _get_scene(job, int(i)) is not None
    )
    return {"status": "ok", "output": str(final), "total_seconds": round(total_s, 1),
            "scenes_merged": len(clips)}


def _tool_finish_video(job: VideoJob, work: Path, args: dict) -> dict:
    summary = str(args.get("summary", ""))
    job.finished = True
    result = {
        "status":        "done",
        "final_mp4":     job.final_mp4,
        "total_scenes":  len(job.scenes),
        "summary":       summary,
    }
    # Write final metadata
    meta = {
        "title":   summary[:80] or job.query,
        "seconds": sum(sc.audio_duration for sc in job.scenes),
        "scenes":  len(job.scenes),
    }
    try:
        (VIDEO_DIR / f"{job.id}.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
    except OSError:
        pass
    return result


def _tool_search_nptel(job: VideoJob, work: Path, args: dict) -> dict:
    query = str(args.get("query", job.query))
    try:
        from core.nptel.search import find_clip
        clip = find_clip(query)
        return {"clip": clip} if clip else {"clip": None, "note": "no NPTEL clip found"}
    except Exception as e:
        return {"clip": None, "error": str(e)}


# ── tool registry ──────────────────────────────────────────────────────────────

TOOL_FNS = {
    "search_textbook":       _tool_search_textbook,
    "set_style":             _tool_set_style,
    "add_scene":             _tool_add_scene,
    "select_background":     _tool_select_background,
    "build_animation":       _tool_build_animation,
    "compute_data":          _tool_compute_data,
    "write_narration":       _tool_write_narration,
    "synthesize_narration":  _tool_synthesize_narration,
    "render_scene":          _tool_render_scene,
    "preview_scene":         _tool_preview_scene,
    "merge_scenes":          _tool_merge_scenes,
    "finish_video":          _tool_finish_video,
    "search_nptel_clip":     _tool_search_nptel,
}


# ── Gemini function declarations ───────────────────────────────────────────────

def _declarations():
    """Return list of google.genai types.Tool with all function declarations."""
    from google.genai import types as _t

    def _fn(name, desc, props, required=None):
        return _t.FunctionDeclaration(
            name=name, description=desc,
            parameters=_t.Schema(
                type=_t.Type.OBJECT,
                properties={k: _t.Schema(**v) for k, v in props.items()},
                required=required or [],
            ),
        )

    S = _t.Type.STRING
    N = _t.Type.NUMBER
    I = _t.Type.INTEGER
    B = _t.Type.BOOLEAN
    O = _t.Type.OBJECT
    A = _t.Type.ARRAY

    decls = [
        _fn("search_textbook", "Search the textbook vector DB. MUST be called first.",
            {"query": {"type": S, "description": "search query"}}, ["query"]),

        _fn("set_style", "Lock the visual style for the whole video.",
            {"palette":         {"type": S, "description": "colour palette name, e.g. dark_tech"},
             "primary_color":   {"type": S, "description": "hex colour, e.g. #7aa2f7"},
             "accent_color":    {"type": S, "description": "hex accent colour"},
             "motion_language": {"type": S, "description": "smooth | snappy | slow"},
             "mood":            {"type": S, "description": "focused | energetic | calm"}},
            []),

        _fn("add_scene", "Create one scene slot. Call 4–7 times to plan the full video.",
            {"type":    {"type": S, "description":
                         "hook|concept_diagram|working_animation|graph|calculation|"
                         "comparison|application|recap"},
             "title":   {"type": S, "description": "short scene heading, max 8 words"},
             "purpose": {"type": S, "description": "one sentence: what the student learns"}},
            ["type", "title", "purpose"]),

        _fn("select_background", "Choose a background for a scene.",
            {"scene_id": {"type": I, "description": "scene id from add_scene"},
             "kind":     {"type": S, "description": "gradient|grid|blueprint|dots|web_image"},
             "query":    {"type": S, "description": "search query for web_image kind"}},
            ["scene_id", "kind"]),

        _fn("build_animation", "Set the visual animation spec for a scene.",
            {"scene_id":       {"type": I, "description": "scene id"},
             "animation_type": {"type": S, "description":
                                "circuit_diagram|device_cross_section|graph|"
                                "equation_steps|flow|bullets|split_compare"},
             "spec":           {"type": O, "description":
                                "animation parameters: for circuit_diagram pass {components:[{type,label}],"
                                "label_in,label_out}; for graph pass {curves:[{xs,ys,label}],x_label,y_label,"
                                "regions,op_point}; for device_cross_section pass {device,layers:[{label,color,"
                                "height}]}; for equation_steps pass {steps:[{equation,explanation}]}; "
                                "for bullets pass {bullets:[str],subtitle}; "
                                "for split_compare pass {panels:[{label,points,color}]}"}},
            ["scene_id", "animation_type", "spec"]),

        _fn("compute_data", "Evaluate a numpy expression safely. Use for ALL numbers shown on screen.",
            {"expression": {"type": S, "description": "numpy expression, e.g. '0.5*k*(vgs-vth)**2'"},
             "variables":  {"type": O, "description": "dict of scalar variable values, e.g. {k:2,vth:1}"},
             "sweep":      {"type": O, "description":
                            "optional: {variable,start,stop,n,log_scale} to sweep one variable"}},
            ["expression"]),

        _fn("write_narration", "Set the spoken narration for a scene (~2.5 words/second).",
            {"scene_id": {"type": I}, "text": {"type": S}}, ["scene_id", "text"]),

        _fn("synthesize_narration", "Run TTS and return real audio duration in seconds.",
            {"scene_id": {"type": I},
             "voice":    {"type": S, "description": "edge-tts voice name, e.g. en-US-AriaNeural"}},
            ["scene_id"]),

        _fn("render_scene", "Render background + animation + narration into an MP4 clip.",
            {"scene_id": {"type": I}}, ["scene_id"]),

        _fn("preview_scene", "Capture a mid-scene frame. Check for blank/overflow. Fix if needed.",
            {"scene_id": {"type": I}}, ["scene_id"]),

        _fn("merge_scenes", "Concatenate all rendered clips into the final video.",
            {"order":      {"type": A, "description": "list of scene_ids in playback order",
                            "items": {"type": I}},
             "transition": {"type": S, "description": "none|fade"}},
            []),

        _fn("finish_video", "End the loop and return the final video.",
            {"summary": {"type": S, "description": "one sentence about what was taught"}},
            ["summary"]),

        _fn("search_nptel_clip", "Optional: find a matching NPTEL lecture clip.",
            {"query": {"type": S}}, ["query"]),
    ]

    return [_t.Tool(function_declarations=decls)]


# ── main agent loop ────────────────────────────────────────────────────────────

def run_video_agent(query: str, level: str, job_id: str,
                    progress_fn=print) -> VideoJob:
    """Run the full agentic video generation loop. Returns a VideoJob."""
    from google import genai
    from google.genai import types

    work = VIDEO_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    (work / "assets").mkdir(exist_ok=True)

    job = VideoJob(id=job_id, query=query, level=level)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model  = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    tools  = _declarations()

    # Seed conversation
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text=AGENT_SYSTEM + f"\n\nStudent query: {query}")]
        )
    ]

    t0 = time.time()
    progress_fn("Agent starting — searching textbook…")
    _write_progress(work, "Agent starting — searching textbook…")

    while job.tool_calls < MAX_TOOL_CALLS and (time.time() - t0) < TIMEOUT_SECONDS:
        if job.finished:
            break
        try:
            resp = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(tools=tools, max_output_tokens=2000),
            )
        except Exception as e:
            job.error = f"LLM error: {e}"
            progress_fn(f"LLM error: {e}")
            break

        if not resp.candidates:
            break

        candidate = resp.candidates[0]
        # Collect all parts from the model response
        model_parts = list(candidate.content.parts)
        contents.append(types.Content(role="model", parts=model_parts))

        # Find function calls in this response
        func_calls = [p for p in model_parts if p.function_call is not None]

        if not func_calls:
            # Model gave a text response without calling tools — done or stuck
            if hasattr(candidate.content, "text") and candidate.content.text:
                progress_fn(f"Agent: {candidate.content.text[:200]}")
            break

        # Execute each tool call and collect results
        result_parts = []
        for fc in func_calls:
            fn_name = fc.function_call.name
            fn_args = dict(fc.function_call.args) if fc.function_call.args else {}
            job.tool_calls += 1

            msg = f"Tool: {fn_name}({', '.join(f'{k}={repr(v)[:30]}' for k,v in fn_args.items())})"
            progress_fn(msg)
            _write_progress(work, msg)

            t_call = time.time()
            fn = TOOL_FNS.get(fn_name)
            if fn is None:
                result = {"error": f"unknown tool: {fn_name}"}
            else:
                try:
                    result = fn(job, work, fn_args)
                except Exception as e:
                    result = {"error": str(e)}

            elapsed = round((time.time() - t_call) * 1000)
            job.trace.append({"tool": fn_name, "args": fn_args,
                               "result": result, "ms": elapsed})
            _write_trace(work, job.trace)

            result_parts.append(types.Part(
                function_response=types.FunctionResponse(
                    name=fn_name,
                    response={"result": result},
                )
            ))

            if fn_name == "finish_video":
                job.finished = True

        contents.append(types.Content(role="user", parts=result_parts))

    # Safety net: if agent ran out of calls/time, merge whatever rendered
    if not job.finished and job.final_mp4 == "":
        progress_fn("Limit reached — merging completed scenes…")
        rendered = [sc.id for sc in job.scenes if sc.done]
        if rendered:
            _tool_merge_scenes(job, work, {"order": rendered})
        _tool_finish_video(job, work, {"summary": f"Partial video for: {query}"})

    return job


# ── private helpers ────────────────────────────────────────────────────────────

def _get_scene(job: VideoJob, sid: int):
    for sc in job.scenes:
        if sc.id == sid:
            return sc
    return None


def _wav_duration(path) -> float:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True,
        )
        return float(r.stdout.strip() or 3.0)


def _make_silent_wav(work: Path, sid: int, duration: float) -> Path:
    """Create a silent WAV file when TTS is unavailable."""
    out = work / f"scene_{sid}_silent.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono",
         "-t", str(duration), str(out)],
        capture_output=True,
    )
    return out


def _render_scene_to_mp4(html: str, duration: float, wav: Path,
                          out_mp4: Path, progress=print) -> None:
    """Playwright → JPEG frames → ffmpeg. Same approach as animate.py."""
    from playwright.sync_api import sync_playwright

    SEEK_JS = ("(t) => { document.querySelectorAll('.anim').forEach(el => {"
               "const s=parseFloat(el.dataset.start||'0');"
               "el.style.animationDelay=(s-t)+'s';});}")

    n_frames = max(int((duration + TAIL_PAD) * FPS), 1)
    err_path = out_mp4.parent / "ffmpeg_scene.log"

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content(html)
        page.wait_for_timeout(80)

        with open(err_path, "wb") as errf:
            proc = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-nostats",
                 "-f", "image2pipe", "-framerate", str(FPS),
                 "-c:v", "mjpeg", "-i", "-",
                 "-i", str(wav),
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                 "-pix_fmt", "yuv420p",
                 "-af", "apad", "-c:a", "aac", "-shortest", str(out_mp4)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errf,
            )
            try:
                for i in range(n_frames):
                    page.evaluate(SEEK_JS, i / FPS)
                    proc.stdin.write(page.screenshot(type="jpeg", quality=80))
                    if i % FPS == 0:
                        progress(f"frame {i+1}/{n_frames}")
                proc.stdin.close()
            except BrokenPipeError:
                pass
            rc = proc.wait()
        browser.close()

    if rc != 0:
        raise RuntimeError(err_path.read_text(errors="replace")[-400:])


def _fetch_wikimedia(query: str, assets_dir: Path) -> tuple:
    """Download a Wikimedia Commons image. Returns (path, description, credit)."""
    try:
        import urllib.request, urllib.parse
        assets_dir.mkdir(parents=True, exist_ok=True)
        q = urllib.parse.quote(query)
        url = (f"https://en.wikipedia.org/w/api.php?action=query&list=search"
               f"&srsearch={q}&srnamespace=6&srlimit=3&format=json")
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return None, "", ""
        title = hits[0]["title"].replace("File:", "")
        # Get image URL
        enc  = urllib.parse.quote(f"File:{title}")
        iurl = (f"https://en.wikipedia.org/w/api.php?action=query&titles={enc}"
                f"&prop=imageinfo&iiprop=url|user|extmetadata&format=json")
        with urllib.request.urlopen(iurl, timeout=5) as r:
            idata = json.loads(r.read())
        pages = list(idata.get("query", {}).get("pages", {}).values())
        if not pages:
            return None, "", ""
        ii = pages[0].get("imageinfo", [{}])[0]
        img_url = ii.get("url", "")
        if not img_url or not img_url.lower().endswith((".jpg", ".jpeg", ".png", ".svg")):
            return None, "", ""
        ext   = img_url.rsplit(".", 1)[-1].lower()
        fname = assets_dir / f"bg_{abs(hash(query))}.{ext}"
        if not fname.exists():
            urllib.request.urlretrieve(img_url, fname)
        meta   = ii.get("extmetadata", {})
        artist = meta.get("Artist", {}).get("value", ii.get("user", "unknown"))
        lic    = meta.get("LicenseShortName", {}).get("value", "unknown licence")
        credit = f"{artist} / Wikimedia Commons / {lic}"
        return fname, title, credit
    except Exception:
        return None, "", ""
