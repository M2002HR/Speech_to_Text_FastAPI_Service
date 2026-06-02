from __future__ import annotations

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_VIDEO = ROOT / "samples" / "03-03-first-5min.mp4"


@pytest.mark.skipif(
    os.getenv("RUN_REAL_SAMPLE_TESTS") != "1",
    reason="set RUN_REAL_SAMPLE_TESTS=1 to run real 5-minute sample transcription",
)
def test_real_sample_video_transcribes_with_local_tiny_model(client_factory) -> None:
    assert SAMPLE_VIDEO.exists(), f"missing sample video: {SAMPLE_VIDEO}"
    assert SAMPLE_VIDEO.stat().st_size > 1_000_000

    ffmpeg_binary = os.getenv("PROCESSING_FFMPEG_BINARY", "ffmpeg")
    ffprobe_binary = os.getenv("PROCESSING_FFPROBE_BINARY", "ffprobe")
    model_dir = str(ROOT / "runtime" / "models")

    with client_factory(
        {
            "STORAGE_MODEL_DIR": model_dir,
            "PROCESSING_FFMPEG_BINARY": ffmpeg_binary,
            "PROCESSING_FFPROBE_BINARY": ffprobe_binary,
            "LOCAL_DEVICE": "cpu",
            "LOCAL_COMPUTE_TYPE": "int8",
            "LOCAL_CPU_THREADS": "4",
            "LOCAL_NUM_WORKERS": "1",
        }
    ) as client:
        with SAMPLE_VIDEO.open("rb") as fh:
            response = client.post(
                "/transcribe",
                data={
                    "provider": "local",
                    "model": "tiny",
                    "language": "fa",
                    "response_format": "verbose_json",
                    "word_timestamps": "false",
                    "segment_timestamps": "false",
                    "beam_size": "1",
                    "best_of": "1",
                    "vad_filter": "false",
                },
                files={"file": (SAMPLE_VIDEO.name, fh, "video/mp4")},
                timeout=900,
            )

    assert response.status_code == 200, response.text[:1000]
    body = response.json()
    assert isinstance(body.get("text"), str)
    assert body["text"].strip()
    assert body["usage"]["provider"] == "local"
    assert body["usage"]["model"] == "tiny"
    assert body["metadata"]["was_video"] is True
