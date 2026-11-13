"""Tests for core/video/tts.py — provider chain, caching, and fallback.

Runs without pytest (uses stdlib unittest). Providers are fully mocked
so no actual TTS synthesis or network calls happen.
"""
import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, call, patch

try:
    import pytest
except ImportError:
    pytest = None  # noqa: F841  — tests use unittest directly

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_silent_wav(path: Path, duration_s: float = 1.0, rate: int = 24000):
    """Write a valid silent mono WAV file for duration checks."""
    import struct
    n_frames = int(rate * duration_s)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *([0] * n_frames)))


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestProviderAvailability(unittest.TestCase):

    def test_gemini_tts_unavailable_without_env(self):
        """GeminiTTSProvider.available() must return False when env vars are absent."""
        with patch.dict("os.environ", {}, clear=True):
            # Temporarily hide the vars
            import os
            os.environ.pop("GEMINI_TTS_MODEL", None)
            os.environ.pop("GEMINI_API_KEY", None)
            # Import fresh with cleared env
            from core.video.tts import GeminiTTSProvider
            p = GeminiTTSProvider.__new__(GeminiTTSProvider)
            p.model = ""
            p.voice = "en-US-Studio-Q"
            self.assertFalse(p.available())

    def test_pyttsx3_provider_available_when_importable(self):
        """Pyttsx3Provider.available() should return True when pyttsx3 can be imported."""
        pyttsx3_mock = MagicMock()
        with patch.dict("sys.modules", {"pyttsx3": pyttsx3_mock}):
            from core.video.tts import Pyttsx3Provider
            p = Pyttsx3Provider()
            self.assertTrue(p.available())

    def test_edge_tts_unavailable_without_package(self):
        """EdgeTTSProvider.available() should return False when edge_tts is missing."""
        with patch.dict("sys.modules", {"edge_tts": None}):
            from core.video.tts import EdgeTTSProvider
            p = EdgeTTSProvider()
            self.assertFalse(p.available())


class TestCacheHit(unittest.TestCase):

    def setUp(self):
        """Reset provider cache and patch CACHE_DIR to a temp dir."""
        import core.video.tts as tts_mod
        tts_mod.reset_provider_cache()
        self._tmp = tempfile.mkdtemp()
        self._orig_cache = tts_mod._CACHE_DIR
        tts_mod._CACHE_DIR = Path(self._tmp)

    def tearDown(self):
        import core.video.tts as tts_mod
        tts_mod._CACHE_DIR = self._orig_cache
        tts_mod.reset_provider_cache()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_cache_hit_skips_synthesis(self):
        """When a cached WAV already exists, synthesize_with_cache copies it without calling the provider."""
        import core.video.tts as tts_mod
        from core.video.tts import EdgeTTSProvider, synthesize_with_cache

        provider = EdgeTTSProvider()
        key = tts_mod._cache_key("hello world", provider.name, provider.voice_id)
        cached_wav = tts_mod._CACHE_DIR / f"{key}.wav"
        tts_mod._CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _make_silent_wav(cached_wav, duration_s=0.5)

        with tempfile.TemporaryDirectory() as work_tmp:
            work = Path(work_tmp)
            out_wav = work / "out.wav"

            # Patch the chain to return edge-tts (available)
            mock_edge = MagicMock(spec=EdgeTTSProvider)
            mock_edge.name = "edge-tts"
            mock_edge.voice_id = provider.voice_id
            mock_edge.available.return_value = True

            with patch.object(tts_mod, "_PROVIDERS", [mock_edge]):
                result = synthesize_with_cache("hello world", out_wav, work, "s0")

            # Provider.synthesize must NOT have been called
            mock_edge.synthesize.assert_not_called()
            self.assertIn("cached", result)
            self.assertTrue(out_wav.exists())

    def test_cache_miss_calls_synthesize_and_writes_cache(self):
        """On a cache miss the provider is called and the result is stored in cache."""
        import core.video.tts as tts_mod
        from core.video.tts import synthesize_with_cache

        tts_mod._CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as work_tmp:
            work = Path(work_tmp)
            out_wav = work / "out.wav"

            def fake_synthesize(text, path, w, stem):
                _make_silent_wav(path, duration_s=1.0)

            mock_provider = MagicMock()
            mock_provider.name = "edge-tts"
            mock_provider.voice_id = "edge:en-US-AriaNeural"
            mock_provider.available.return_value = True
            mock_provider.synthesize.side_effect = fake_synthesize

            with patch.object(tts_mod, "_PROVIDERS", [mock_provider]):
                result = synthesize_with_cache("ohm's law", out_wav, work, "s1")

            mock_provider.synthesize.assert_called_once()
            self.assertNotIn("cached", result)
            self.assertTrue(out_wav.exists())

            # Cache file must now exist
            key = tts_mod._cache_key("ohm's law", mock_provider.name, mock_provider.voice_id)
            self.assertTrue((tts_mod._CACHE_DIR / f"{key}.wav").exists())


class TestFallback(unittest.TestCase):

    def setUp(self):
        import core.video.tts as tts_mod
        tts_mod.reset_provider_cache()
        self._tmp = tempfile.mkdtemp()
        self._orig_cache = tts_mod._CACHE_DIR
        tts_mod._CACHE_DIR = Path(self._tmp)
        tts_mod._CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import core.video.tts as tts_mod
        tts_mod._CACHE_DIR = self._orig_cache
        tts_mod.reset_provider_cache()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_fallback_to_next_provider_on_failure(self):
        """When the primary provider raises, synthesize_with_cache falls back to the next one."""
        import core.video.tts as tts_mod
        from core.video.tts import synthesize_with_cache

        def fake_ok(text, path, w, stem):
            _make_silent_wav(path, duration_s=1.0)

        primary = MagicMock()
        primary.name = "gemini-tts"
        primary.voice_id = "gemini:g:v"
        primary.available.return_value = True
        primary.synthesize.side_effect = RuntimeError("network error")

        fallback = MagicMock()
        fallback.name = "pyttsx3"
        fallback.voice_id = "pyttsx3:offline"
        fallback.available.return_value = True
        fallback.synthesize.side_effect = fake_ok

        with tempfile.TemporaryDirectory() as work_tmp:
            work = Path(work_tmp)
            out_wav = work / "out.wav"

            with patch.object(tts_mod, "_PROVIDERS", [primary, fallback]):
                result = synthesize_with_cache("hello", out_wav, work, "s2")

        primary.synthesize.assert_called_once()
        fallback.synthesize.assert_called_once()
        self.assertEqual(result, "pyttsx3")

    def test_all_providers_exhausted_raises(self):
        """If every provider fails, synthesize_with_cache should raise RuntimeError."""
        import core.video.tts as tts_mod
        from core.video.tts import synthesize_with_cache

        bad = MagicMock()
        bad.name = "edge-tts"
        bad.voice_id = "edge:x"
        bad.available.return_value = True
        bad.synthesize.side_effect = RuntimeError("boom")

        with tempfile.TemporaryDirectory() as work_tmp:
            work = Path(work_tmp)
            out_wav = work / "out.wav"

            with patch.object(tts_mod, "_PROVIDERS", [bad]):
                with self.assertRaises(RuntimeError):
                    synthesize_with_cache("test", out_wav, work, "s3")


class TestAudioDuration(unittest.TestCase):

    def test_audio_duration_silent_wav(self):
        """audio_duration() should return the correct duration for a synthesized WAV."""
        from core.video.animate import audio_duration

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "test.wav"
            _make_silent_wav(wav, duration_s=2.0, rate=24000)
            dur = audio_duration(wav)
            self.assertAlmostEqual(dur, 2.0, delta=0.1)


class TestProviderChainOrder(unittest.TestCase):

    def setUp(self):
        import core.video.tts as tts_mod
        tts_mod.reset_provider_cache()

    def tearDown(self):
        import core.video.tts as tts_mod
        tts_mod.reset_provider_cache()

    def test_chain_order_gemini_first(self):
        """get_tts_provider returns GeminiTTS when GEMINI_TTS_MODEL is set."""
        import os
        import core.video.tts as tts_mod

        with patch.dict(os.environ, {"GEMINI_TTS_MODEL": "gemini-2.0-flash-tts", "GEMINI_API_KEY": "x"}):
            tts_mod.reset_provider_cache()
            # patch pyttsx3 and edge_tts as available
            with patch.dict("sys.modules", {"pyttsx3": MagicMock(), "edge_tts": MagicMock()}):
                provider = tts_mod.get_tts_provider()
                self.assertEqual(provider.name, "gemini-tts")

    def test_chain_skips_unavailable(self):
        """When GeminiTTS and EdgeTTS are unavailable, Pyttsx3 is returned."""
        import os
        import core.video.tts as tts_mod

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_TTS_MODEL", None)
            os.environ.pop("GEMINI_API_KEY", None)
            tts_mod.reset_provider_cache()

            with patch.dict("sys.modules", {"edge_tts": None, "pyttsx3": MagicMock()}):
                tts_mod.reset_provider_cache()
                chain = tts_mod._build_chain()
                names = [p.name for p in chain]
                # Pyttsx3 must be in the chain; gemini-tts must not
                self.assertIn("pyttsx3", names)
                self.assertNotIn("gemini-tts", names)
                self.assertNotIn("edge-tts", names)


if __name__ == "__main__":
    unittest.main()
