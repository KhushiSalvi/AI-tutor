"""Modular TTS provider chain for EE Tutor.

Priority order (highest to lowest):
  1. GeminiTTSProvider  — cloud, high quality; requires GEMINI_TTS_MODEL env var
  2. EdgeTTSProvider    — cloud, neural; requires internet
  3. Pyttsx3Provider    — offline Windows voice; always available

synth_with_cache(text, out_wav, work, stem, log) is the single entry point used
by animate.py.  Results are cached in data/tts_cache/ keyed by SHA-256 of
(text, provider_name, voice/model).  On cache hit the .wav is copied instantly.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import wave
from abc import ABC, abstractmethod
from pathlib import Path

# ---------------------------------------------------------------------------
# Cache directory (relative to the module so it works from any cwd)
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent      # ee-tutor/
_CACHE_DIR = _PROJECT_ROOT / "data" / "tts_cache"


def _ensure_cache():
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(text: str, provider: str, voice: str) -> str:
    raw = f"{provider}|{voice}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _run(cmd, what):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{what} failed: {(r.stderr or '')[-600:]}")


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class TTSProvider(ABC):
    """Abstract base for TTS providers."""

    name: str = "base"

    @property
    def voice_id(self) -> str:
        """Unique identifier used in cache key (voice + model)."""
        return self.name

    @abstractmethod
    def synthesize(self, text: str, out_wav: Path, work: Path, stem: str) -> None:
        """Write narrated speech to *out_wav* (16/24 kHz mono WAV)."""
        ...

    def available(self) -> bool:
        """Return False if this provider cannot be used (missing deps / creds)."""
        return True


# ---------------------------------------------------------------------------
# Provider 1 — Gemini TTS
# ---------------------------------------------------------------------------

class GeminiTTSProvider(TTSProvider):
    """Uses Gemini text-to-speech API.

    Works with just GEMINI_API_KEY (no GEMINI_TTS_MODEL env var needed).
    Uses gemini-2.5-flash-preview-tts as the default TTS model, or
    GEMINI_TTS_MODEL if explicitly set.
    """

    name = "gemini-tts"

    # Default TTS model — available on all Gemini API keys
    DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
    DEFAULT_VOICE = "Kore"   # clear, neutral English voice

    def __init__(self):
        import os
        # Allow override via env var, but fall back to our working default
        self.model = os.environ.get("GEMINI_TTS_MODEL", self.DEFAULT_TTS_MODEL)
        self.voice = os.environ.get("GEMINI_TTS_VOICE", self.DEFAULT_VOICE)

    @property
    def voice_id(self) -> str:
        return f"gemini:{self.model}:{self.voice}"

    def available(self) -> bool:
        import os
        return bool(os.environ.get("GEMINI_API_KEY"))

    def synthesize(self, text: str, out_wav: Path, work: Path, stem: str) -> None:
        """Call Gemini TTS and save as WAV using the Google GenAI SDK."""
        import os, wave, struct
        from google import genai
        from google.genai import types

        api_key = os.environ["GEMINI_API_KEY"]
        client = genai.Client(api_key=api_key)

        # Gemini TTS returns raw PCM audio (LINEAR16, 24000 Hz, mono)
        response = client.models.generate_content(
            model=self.model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.voice,
                        )
                    )
                ),
            ),
        )

        # Extract audio bytes
        audio_part = response.candidates[0].content.parts[0]
        raw_audio = audio_part.inline_data.data        # bytes, raw PCM s16le
        mime = audio_part.inline_data.mime_type or ""  # e.g. "audio/L16;rate=24000"

        # Parse sample rate from MIME if present
        sample_rate = 24000
        if "rate=" in mime:
            try:
                sample_rate = int(mime.split("rate=")[1].split(";")[0].strip())
            except (ValueError, IndexError):
                pass

        # Write raw PCM to WAV (since it's already s16le mono)
        raw_path = work / f"{stem}_gemini_raw.pcm"
        raw_path.write_bytes(raw_audio)

        _run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
             "-i", str(raw_path),
             "-ar", "24000", "-ac", "1", str(out_wav)],
            "gemini-tts-pcm-to-wav",
        )
        raw_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Provider 2 — edge-tts (neural cloud voice)
# ---------------------------------------------------------------------------

class EdgeTTSProvider(TTSProvider):
    """Microsoft edge-tts neural voice (requires internet + edge-tts package)."""

    name = "edge-tts"

    def __init__(self):
        import os
        self.voice = os.environ.get("EDGE_TTS_VOICE", "en-US-AriaNeural")

    @property
    def voice_id(self) -> str:
        return f"edge:{self.voice}"

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, out_wav: Path, work: Path, stem: str) -> None:
        import asyncio
        import edge_tts

        mp3 = work / f"{stem}.mp3"

        async def go():
            await asyncio.wait_for(
                edge_tts.Communicate(text, self.voice).save(str(mp3)), timeout=90
            )

        asyncio.run(go())
        _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(out_wav)],
            "mp3->wav",
        )
        mp3.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Provider 3 — pyttsx3 (offline Windows built-in voice)
# ---------------------------------------------------------------------------

class Pyttsx3Provider(TTSProvider):
    """Windows built-in offline TTS via pyttsx3.

    One call per sentence to work around pyttsx3's truncation bug.
    """

    name = "pyttsx3"

    @property
    def voice_id(self) -> str:
        return "pyttsx3:offline"

    def available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, out_wav: Path, work: Path, stem: str) -> None:
        import pyttsx3

        sentences = (
            [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]
            or [text.strip() or "."]
        )
        parts: list[Path] = []
        for i, sent in enumerate(sentences):
            part = work / f"{stem}_part{i}.wav"
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.save_to_file(sent, str(part))
            engine.runAndWait()
            engine.stop()
            parts.append(part)

        if len(parts) == 1:
            shutil.copy2(str(parts[0]), str(out_wav))
            parts[0].unlink(missing_ok=True)
            return

        lst = work / f"{stem}_concat.txt"
        lst.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in parts),
            encoding="utf-8",
        )
        _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), str(out_wav)],
            "join sentences",
        )
        for p in parts:
            p.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Provider chain builder
# ---------------------------------------------------------------------------

_PROVIDERS: list[TTSProvider] | None = None


def _build_chain() -> list[TTSProvider]:
    """Return providers in priority order, filtered to available ones."""
    all_providers: list[TTSProvider] = [
        GeminiTTSProvider(),
        EdgeTTSProvider(),
        Pyttsx3Provider(),
    ]
    return [p for p in all_providers if p.available()]


def get_tts_provider() -> TTSProvider:
    """Return the first available provider (cached after first call)."""
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = _build_chain()
    if not _PROVIDERS:
        raise RuntimeError("No TTS provider available (need pyttsx3, edge-tts, or Gemini TTS).")
    return _PROVIDERS[0]


def reset_provider_cache():
    """Force re-evaluation of available providers (useful in tests)."""
    global _PROVIDERS
    _PROVIDERS = None


# ---------------------------------------------------------------------------
# Fallback walk (used when the top provider fails mid-render)
# ---------------------------------------------------------------------------

def _get_fallback(current: TTSProvider) -> TTSProvider | None:
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = _build_chain()
    try:
        idx = next(i for i, p in enumerate(_PROVIDERS) if p.name == current.name)
        return _PROVIDERS[idx + 1] if idx + 1 < len(_PROVIDERS) else None
    except StopIteration:
        return None


# ---------------------------------------------------------------------------
# Cached synthesis (main entry point)
# ---------------------------------------------------------------------------

def synthesize_with_cache(
    text: str,
    out_wav: Path,
    work: Path,
    stem: str,
    log=print,
) -> str:
    """Synthesize *text* to *out_wav*, using the disk cache when possible.

    Returns the name of the provider that produced the audio.
    """
    _ensure_cache()

    provider = get_tts_provider()
    key = _cache_key(text, provider.name, provider.voice_id)
    cached = _CACHE_DIR / f"{key}.wav"

    if cached.exists():
        shutil.copy2(str(cached), str(out_wav))
        log(f"TTS cache hit ({provider.name}): {key[:12]}…")
        return f"{provider.name} (cached)"

    # Try the provider chain on failure
    while provider is not None:
        try:
            provider.synthesize(text, out_wav, work, stem)
            # Persist to cache
            try:
                shutil.copy2(str(out_wav), str(cached))
            except Exception as ce:
                log(f"TTS cache write failed (non-fatal): {ce}")
            return provider.name
        except Exception as e:
            log(f"{provider.name} failed ({type(e).__name__}: {e}); trying next provider…")
            provider = _get_fallback(provider)

    raise RuntimeError("All TTS providers exhausted — cannot synthesize audio.")
