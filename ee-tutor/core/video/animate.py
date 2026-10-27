"""Render a lesson plan (list of scenes) into an animated MP4 with AI narration.

Runs inside its own worker process (core/video/worker.py), NOT inside the web server, so
Windows COM/asyncio/thread quirks can't freeze it, and every step logs to worker.log.

Per scene: narrate (edge-tts neural voice, falls back to the offline Windows voice) -> measure the
real audio length -> draw the HTML/CSS animation frame by frame in headless Chromium -> pipe the
frames straight into ffmpeg together with the audio. Scenes are then joined into one mp4.
"""
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

from core.video.templates import render_scene_html

FPS = 12
TAIL_PAD = 0.6          # hold the last frame a moment so animations never cut off mid-motion
JPEG_QUALITY = 80
EDGE_VOICE = "en-US-AriaNeural"   # other voices: run  edge-tts --list-voices

SEEK_JS = """(t) => {
    document.querySelectorAll('.anim').forEach(el => {
        const start = parseFloat(el.dataset.start || '0');
        el.style.animationDelay = (start - t) + 's';
    });
}"""

_edge_broken = False


def _run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed: {(r.stderr or '')[-600:]}")


def _tts_edge(text, out_wav, work, stem):
    import asyncio
    import edge_tts

    mp3 = work / f"{stem}.mp3"

    async def go():
        await asyncio.wait_for(edge_tts.Communicate(text, EDGE_VOICE).save(str(mp3)), timeout=90)

    asyncio.run(go())
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)], "mp3->wav")
    mp3.unlink(missing_ok=True)


def _tts_offline(text, out_wav, work, stem):
    """Windows built-in voice. One call per sentence (a single long call can cut speech short)."""
    import pyttsx3

    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()] or [text.strip() or "."]
    parts = []
    for i, sent in enumerate(sentences):
        part = work / f"{stem}_part{i}.wav"
        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.save_to_file(sent, str(part))
        engine.runAndWait()
        engine.stop()
        parts.append(part)
    if len(parts) == 1:
        parts[0].replace(out_wav)
        return
    lst = work / f"{stem}_concat.txt"
    lst.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in parts), encoding="utf-8")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), str(out_wav)], "join sentences")
    for p in parts:
        p.unlink(missing_ok=True)
    lst.unlink(missing_ok=True)


def synth_audio(text, out_wav, work, stem, log=print):
    global _edge_broken
    if not _edge_broken:
        try:
            _tts_edge(text, out_wav, work, stem)
            return "edge-tts"
        except Exception as e:  # no internet / package missing -> use the offline voice from now on
            _edge_broken = True
            log(f"edge-tts unavailable ({type(e).__name__}: {e}); using the offline Windows voice instead")
    _tts_offline(text, out_wav, work, stem)
    return "offline voice"


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
    with open(err_path, "wb") as errf:      # ffmpeg's messages go to a file, so a full pipe can never block it
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


def build_video(scenes, out_dir, video_id, progress=print):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg was not found on PATH. Install it and open a NEW terminal before starting uvicorn.")
    from playwright.sync_api import sync_playwright

    work = Path(out_dir) / video_id
    work.mkdir(parents=True, exist_ok=True)
    n, t0 = len(scenes), time.time()

    # 1) narration for every scene first (the voice engine must not run inside the browser engine's event loop)
    audio = []
    for i, sc in enumerate(scenes, 1):
        progress(f"Scene {i}/{n}: recording narration…")
        wav = work / f"scene_{i}.wav"
        engine = synth_audio(sc["narration"], wav, work, f"scene_{i}", log=progress)
        audio.append((wav, max(audio_duration(wav), 1.5), engine))
    print(f"narration done after {time.time() - t0:.0f}s ({audio[0][2]})", flush=True)

    # 2) draw each scene's animation and encode it together with its narration
    total, clips = 0.0, []
    with sync_playwright() as p:
        progress("Starting the animation engine…")
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for i, (sc, (wav, dur, _engine)) in enumerate(zip(scenes, audio), 1):
            total += dur
            clip = work / f"scene_{i}.mp4"
            render_scene(page, render_scene_html(sc, i, n), dur, clip, wav, work, f"Scene {i}/{n}", progress)
            clips.append(clip)
            print(f"Scene {i}/{n} done after {time.time() - t0:.0f}s", flush=True)
        browser.close()

    progress("Joining scenes into the final video…")
    lst = work / "concat.txt"
    lst.write_text("\n".join(f"file '{c.resolve().as_posix()}'" for c in clips), encoding="utf-8")
    final = Path(out_dir) / f"{video_id}.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(final)], "joining scenes")
    return final, total
