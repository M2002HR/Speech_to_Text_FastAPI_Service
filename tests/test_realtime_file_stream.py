from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import websockets

from api.app.config import get_settings
from api.app.live_analysis import BrowserSender, LiveSessionState
from api.app.live_settings import LiveSettings
from api.app.live_stt import connect_deepgram, deepgram_to_browser, keepalive_loop
from api.app.realtime_router import _file_stream_settings, _file_to_deepgram


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_VIDEO = ROOT / "samples" / "03-03-first-5min.mp4"


# --------------------------------------------------------------------------- #
# The actual bug: the websockets client keepalive ping must be OFF for Deepgram
# (it does not answer protocol pings -> spurious 1011 "keepalive ping timeout").
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_connect_deepgram_disables_ws_ping_when_interval_non_positive(monkeypatch):
    captured = {}

    async def fake_connect(url, additional_headers=None, **kwargs):
        captured.clear()
        captured.update(kwargs)
        captured["url"] = url
        return object()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    settings = replace(LiveSettings(), ping_interval_sec=0.0, connect_retries=1)
    await connect_deepgram("wss://api.deepgram.com/v1/listen", "key", settings)
    assert captured["ping_interval"] is None
    assert captured["ping_timeout"] is None


@pytest.mark.asyncio
async def test_connect_deepgram_respects_explicit_positive_ping(monkeypatch):
    captured = {}

    async def fake_connect(url, additional_headers=None, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(websockets, "connect", fake_connect)

    settings = replace(LiveSettings(), ping_interval_sec=20.0, ping_timeout_sec=20.0, connect_retries=1)
    await connect_deepgram("wss://api.deepgram.com/v1/listen", "key", settings)
    assert captured["ping_interval"] == 20.0
    assert captured["ping_timeout"] == 20.0


def test_default_ping_interval_is_disabled():
    # Default config must not re-introduce the keepalive-ping-timeout bug.
    assert LiveSettings().ping_interval_sec == 0.0
    assert LiveSettings.from_env().ping_interval_sec == 0.0


# --------------------------------------------------------------------------- #
# End-to-end file playback pipeline against a fake Deepgram socket, using a
# short clip cut from the real sample video. Exercises ffmpeg decode + paced
# streaming + transcript forwarding without needing a live Deepgram key.
# --------------------------------------------------------------------------- #
class _FakeBrowserWS:
    def __init__(self, app_settings):
        self.app = SimpleNamespace(state=SimpleNamespace(settings=app_settings))
        self.events = []

    async def send_json(self, message):
        self.events.append(message)


class _FakeDeepgram:
    """Records audio sent to Deepgram and emits one final transcript."""

    def __init__(self):
        self.sent_bytes = 0
        self.sent_text = []
        self.closed = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._emitted = False

    async def send(self, data):
        if isinstance(data, (bytes, bytearray)):
            self.sent_bytes += len(data)
            if not self._emitted:
                self._emitted = True
                await self._queue.put(
                    json.dumps(
                        {
                            "type": "Results",
                            "is_final": True,
                            "speech_final": True,
                            "start": 0.0,
                            "duration": 1.0,
                            "channel": {
                                "alternatives": [
                                    {"transcript": "نمونه متن", "confidence": 0.95, "words": []}
                                ]
                            },
                        }
                    )
                )
            return
        text = str(data)
        self.sent_text.append(text)
        if "CloseStream" in text:
            self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            if not self._queue.empty():
                return self._queue.get_nowait()
            if self.closed:
                raise StopAsyncIteration
            await asyncio.sleep(0.01)

    async def close(self):
        self.closed = True


def _make_short_clip(dest_dir: Path) -> Path:
    ffmpeg = os.getenv("PROCESSING_FFMPEG_BINARY", "ffmpeg")
    clip = dest_dir / "clip.wav"
    proc = subprocess.run(
        [
            ffmpeg, "-v", "error", "-y",
            "-i", str(SAMPLE_VIDEO),
            "-t", "2",
            "-vn", "-ac", "1", "-ar", "16000",
            str(clip),
        ],
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[:500]
    assert clip.exists() and clip.stat().st_size > 1000
    return clip


@pytest.mark.asyncio
async def test_file_playback_streams_sample_without_ping_timeout():
    if shutil.which(os.getenv("PROCESSING_FFMPEG_BINARY", "ffmpeg")) is None:
        pytest.skip("ffmpeg not available")
    if not SAMPLE_VIDEO.exists():
        pytest.skip(f"sample video missing: {SAMPLE_VIDEO}")

    with tempfile.TemporaryDirectory() as tmp:
        clip = _make_short_clip(Path(tmp))

        app_settings = get_settings()
        settings = _file_stream_settings(replace(LiveSettings(), llm_enabled=False, llm_api_key=""))
        ws = _FakeBrowserWS(app_settings)
        dg = _FakeDeepgram()
        state = LiveSessionState(session_id="test-session")
        sender = BrowserSender(ws)
        sender.start()
        stop_event = asyncio.Event()

        async def run():
            file_task = asyncio.create_task(
                _file_to_deepgram(ws, sender, dg, state, settings, clip, stop_event)
            )
            receiver = asyncio.create_task(
                deepgram_to_browser(ws, sender, dg, state, settings, stop_event)
            )
            keepalive = asyncio.create_task(keepalive_loop(dg, settings, stop_event))
            await file_task
            await asyncio.wait_for(receiver, timeout=10.0)
            stop_event.set()
            keepalive.cancel()
            await sender.aclose()

        await asyncio.wait_for(run(), timeout=30.0)

    event_types = [e["type"] for e in ws.events]

    # Audio actually streamed to Deepgram and the stream was closed cleanly.
    assert dg.sent_bytes > 16000, f"expected real PCM bytes, got {dg.sent_bytes}"
    assert any("CloseStream" in t for t in dg.sent_text)

    # Playback lifecycle events and a forwarded transcript reached the browser.
    assert "file.playback.started" in event_types
    assert "file.playback.finished" in event_types
    assert "transcript.final" in event_types

    # The bug under test must not surface.
    assert "file.playback.error" not in event_types
    assert "error" not in event_types


# --------------------------------------------------------------------------- #
# net0001 regression: a slow browser flooded with interim results must NOT be
# able to stall the audio->Deepgram path. Previously every browser write went
# through one shared lock that the audio sender also grabbed at each progress
# checkpoint, so a slow browser starved audio long enough for Deepgram to drop
# the stream with "net0001 (no audio within timeout window)". The BrowserSender
# queue must keep audio flowing regardless of browser speed.
# --------------------------------------------------------------------------- #
class _SlowBrowserWS:
    def __init__(self, app_settings, delay):
        self.app = SimpleNamespace(state=SimpleNamespace(settings=app_settings))
        self.events = []
        self._delay = delay

    async def send_json(self, message):
        await asyncio.sleep(self._delay)  # simulate a slow/janky browser client
        self.events.append(message)


class _FloodDeepgram:
    """Models a full-duplex Deepgram socket that floods interim results.

    Crucially it emulates real backpressure: if the client stops reading our
    results (because deepgram_to_browser is blocked on a slow browser), our
    receive buffer toward the client fills and we can no longer accept audio.
    That is exactly the coupling that produced net0001 in production — a slow
    browser stalling the audio path. The fix must keep the client draining us
    fast enough that audio never stalls.
    """

    def __init__(self, loop, *, backlog=8):
        self.audio_sends = 0
        self.sent_text = []
        self.closed = False
        self.max_gap = 0.0
        self._last_audio_at = None
        self._loop = loop
        self._backlog = backlog
        self._queue: asyncio.Queue = asyncio.Queue()

    async def send(self, data):
        if isinstance(data, (bytes, bytearray)):
            # Full-duplex backpressure: block accepting audio while the client
            # has not drained our outgoing results.
            while self._queue.qsize() >= self._backlog and not self.closed:
                await asyncio.sleep(0.005)
            now = self._loop.time()
            if self._last_audio_at is not None:
                self.max_gap = max(self.max_gap, now - self._last_audio_at)
            self._last_audio_at = now
            self.audio_sends += 1
            for i in range(4):
                self._queue.put_nowait(
                    json.dumps(
                        {
                            "type": "Results",
                            "is_final": False,
                            "channel": {"alternatives": [{"transcript": f"part {self.audio_sends}.{i}", "words": []}]},
                        }
                    )
                )
            self._queue.put_nowait(
                json.dumps(
                    {
                        "type": "Results",
                        "is_final": True,
                        "speech_final": True,
                        "start": 0.0,
                        "duration": 0.25,
                        "channel": {"alternatives": [{"transcript": f"final {self.audio_sends}", "words": []}]},
                    }
                )
            )
            return
        text = str(data)
        self.sent_text.append(text)
        if "CloseStream" in text:
            self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            if not self._queue.empty():
                return self._queue.get_nowait()
            if self.closed:
                raise StopAsyncIteration
            await asyncio.sleep(0.005)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_slow_browser_does_not_starve_audio_to_deepgram():
    if shutil.which(os.getenv("PROCESSING_FFMPEG_BINARY", "ffmpeg")) is None:
        pytest.skip("ffmpeg not available")
    if not SAMPLE_VIDEO.exists():
        pytest.skip(f"sample video missing: {SAMPLE_VIDEO}")

    with tempfile.TemporaryDirectory() as tmp:
        # ~6 seconds of audio so we cross several 5s progress checkpoints.
        ffmpeg = os.getenv("PROCESSING_FFMPEG_BINARY", "ffmpeg")
        clip = Path(tmp) / "clip6.wav"
        proc = subprocess.run(
            [ffmpeg, "-v", "error", "-y", "-i", str(SAMPLE_VIDEO), "-t", "6", "-vn", "-ac", "1", "-ar", "16000", str(clip)],
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[:500]

        loop = asyncio.get_running_loop()
        app_settings = get_settings()
        settings = _file_stream_settings(replace(LiveSettings(), llm_enabled=False, llm_api_key=""))
        ws = _SlowBrowserWS(app_settings, delay=0.1)  # slow browser
        dg = _FloodDeepgram(loop)
        state = LiveSessionState(session_id="starve-test")
        sender = BrowserSender(ws)
        sender.start()
        stop_event = asyncio.Event()

        playback_wall = {}

        async def run():
            started = loop.time()
            file_task = asyncio.create_task(_file_to_deepgram(ws, sender, dg, state, settings, clip, stop_event))
            receiver = asyncio.create_task(deepgram_to_browser(ws, sender, dg, state, settings, stop_event))
            keepalive = asyncio.create_task(keepalive_loop(dg, settings, stop_event))
            await file_task
            # Audio playback latency is what the user perceives and what governs
            # Deepgram's net0001 timeout; measure it before flushing the browser.
            playback_wall["seconds"] = loop.time() - started
            stop_event.set()
            receiver.cancel()
            keepalive.cancel()
            await sender.aclose()

        await asyncio.wait_for(run(), timeout=40.0)

    wall = playback_wall["seconds"]

    # Audio must have streamed continuously: no multi-second gap that would
    # trip Deepgram's net0001 timeout, even though the browser was slow and
    # flooded with interim results.
    assert dg.audio_sends > 10
    assert dg.max_gap < 2.0, f"audio to Deepgram stalled for {dg.max_gap:.2f}s (net0001 risk)"
    # And playback stays close to ~1x realtime (6s clip): a slow browser must
    # not drag audio playback out (the original "very slow" symptom).
    assert wall < 9.0, f"playback took {wall:.1f}s for a 6s clip (slow browser starved audio)"
    assert any("CloseStream" in t for t in dg.sent_text)
