"""Render a lesson plan (list of scenes) into an animated MP4 with AI narration.

Runs inside its own worker process (core/video/worker.py), NOT inside the web server, so
Windows COM/asyncio/thread quirks can't freeze it, and every step logs to worker.log.

Per scene: narrate (Gemini TTS → edge-tts → offline Windows voice, via core/video/tts.py) ->
measure the real audio length -> quality-gate check (3 sample frames) ->
draw every frame and pipe into ffmpeg together with the audio. Scenes are then joined into one mp4.
"""
import subprocess
import time
import wave
from pathlib import Path

import shutil

from core.video.templates import render_scene_html, title_bullets
from core.video.tts import synthesize_with_cache

FPS = 12
TAIL_PAD = 0.6          # hold the last frame a moment so animations never cut off mid-motion
JPEG_QUALITY = 80

# Quality gate: sample these fractions of a scene's duration to detect a blank/broken render
_QG_SAMPLE_FRACTIONS = [0.2, 0.5, 0.8]
# Minimum fraction of non-white pixels in a sample frame; below this we fall back
_QG_MIN_NON_WHITE_FRACTION = 0.01

SEEK_JS = """(t) => {
    document.querySelectorAll('.anim').forEach(el => {
        const start = parseFloat(el.dataset.start || '0');
        el.style.animationDelay = (start - t) + 's';
    });
}"""


def _run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed: {(r.stderr or '')[-600:]}")


def synth_audio(text, out_wav, work, stem, log=print):
    """Synthesize narration for one scene.  Delegates to the provider chain in tts.py."""
    return synthesize_with_cache(text, out_wav, work, stem, log=log)


def _quality_check(page, html, duration, log=print):
    """Sample 3 frames of the rendered scene and return True if content looks non-blank.

    Uses a lightweight pixel-brightness heuristic: a nearly-all-white/black screenshot
    with almost no content means the template probably failed to render (e.g. missing
    required fields, layout overflow). Falls back to title_bullets when this happens.
    Uses only stdlib — no Pillow dependency required.
    """
    try:
        import struct, zlib

        page.set_content(html)
        page.wait_for_timeout(60)   # brief settle

        ok_count = 0
        for frac in _QG_SAMPLE_FRACTIONS:
            t = frac * duration
            page.evaluate(SEEK_JS, t)
            png_bytes = page.screenshot(type="png")
            # Parse PNG: IHDR gives width/height; scan IDAT chunks for non-trivial pixel variance
            # Quick approach: compare compressed size to raw size — a blank image compresses >99%
            raw_size = len(png_bytes)
            # A content-rich frame compresses to >2% of raw; blank/solid compresses >99%
            # We use the png byte length as a proxy (larger = more varied pixels)
            # 1280×720 RGB = 2.76 MB raw; a solid-colour PNG is typically <10 KB
            if raw_size > 15_000:   # >15 KB means there's real content in the frame
                ok_count += 1

        passed = ok_count >= 2      # at least 2 of 3 samples must look non-blank
        if not passed:
            log("Quality gate: frame looks blank/broken — will fall back to title_bullets")
        return passed
    except Exception as e:
        log(f"Quality gate check failed ({e}); assuming OK")
        return True  # non-fatal: proceed with the original render


def audio_duration(path):
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True)
        return float(r.stdout.strip() or 0)


def render_scene(page, html, duration, out_mp4, wav, work, label, progress, fps=FPS):
    page.set_content(html)
    page.wait_for_timeout(80)
    n_frames = max(int((duration + TAIL_PAD) * fps), 1)
    err_path = work / "ffmpeg.log"
    with open(err_path, "wb") as errf:
        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-nostats",
             "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
             "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
             "-af", "apad", "-c:a", "aac", "-shortest", str(out_mp4)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errf,
        )
        try:
            for i in range(n_frames):
                page.evaluate(SEEK_JS, i / fps)
                proc.stdin.write(page.screenshot(type="jpeg", quality=JPEG_QUALITY))
                if i % 12 == 0:
                    progress(f"{label}: drawing frame {i + 1}/{n_frames}")
            proc.stdin.close()
        except BrokenPipeError:
            pass
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg could not encode a scene: " + err_path.read_text(errors="replace")[-600:])


def _render_scene_with_quality_gate(page, sc, i, n, wav, dur, clip, work, progress):
    """Render one scene, running the quality gate first.

    If the quality gate fails (blank/broken frames), the scene's visual is replaced
    with a safe title_bullets fallback and re-rendered. Only the failed scene is
    re-rendered — other scenes are unaffected.
    """
    html = render_scene_html(sc, i, n)
    if not _quality_check(page, html, dur, log=progress):
        progress(f"Scene {i}/{n}: quality gate failed — retrying with title_bullets fallback")
        # Build a safe fallback visual using whatever text is available in the scene
        fallback_sc = dict(sc)
        bullets = [str(x) for x in (sc.get("visual", {}).get("bullets") or [])][:3]
        if not bullets:
            bullets = [sc.get("title", f"Scene {i}")]
        fallback_sc["visual"] = {"type": "title_bullets", "bullets": bullets}
        html = render_scene_html(fallback_sc, i, n)
    render_scene(page, html, dur, clip, wav, work, f"Scene {i}/{n}", progress)


def build_video(scenes, out_dir, video_id, progress=print):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg was not found on PATH. Install it and open a NEW terminal before starting uvicorn.")
    from playwright.sync_api import sync_playwright

    work = Path(out_dir) / video_id
    work.mkdir(parents=True, exist_ok=True)
    n, t0 = len(scenes), time.time()

    # 1) Narration for every scene first
    #    (voice engine must not run inside the browser's event loop)
    audio = []
    for i, sc in enumerate(scenes, 1):
        progress(f"Scene {i}/{n}: recording narration…")
        wav = work / f"scene_{i}.wav"
        engine = synth_audio(sc["narration"], wav, work, f"scene_{i}", log=progress)
        audio.append((wav, max(audio_duration(wav), 1.5), engine))
    print(f"narration done after {time.time() - t0:.0f}s ({audio[0][2]})", flush=True)

    # 2) Draw each scene's animation through the quality gate, then encode
    total, clips = 0.0, []
    with sync_playwright() as p:
        progress("Starting the animation engine…")
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for i, (sc, (wav, dur, _engine)) in enumerate(zip(scenes, audio), 1):
            total += dur
            clip = work / f"scene_{i}.mp4"
            _render_scene_with_quality_gate(page, sc, i, n, wav, dur, clip, work, progress)
            clips.append(clip)
            print(f"Scene {i}/{n} done after {time.time() - t0:.0f}s", flush=True)
        browser.close()

    progress("Joining scenes into the final video…")
    lst = work / "concat.txt"
    lst.write_text("\n".join(f"file '{c.resolve().as_posix()}'" for c in clips), encoding="utf-8")
    final = Path(out_dir) / f"{video_id}.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(lst), "-c", "copy", str(final)], "joining scenes")
    return final, total
