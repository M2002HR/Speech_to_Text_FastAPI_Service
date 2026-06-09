# Realtime classroom STT

This branch adds a production-oriented realtime path next to the existing file/job transcription API.

## Run

Use the ASGI entrypoint that includes the existing FastAPI app plus the realtime router:

```bash
uvicorn api.app.asgi:app --host 0.0.0.0 --port 8030 --reload
```

Open:

```text
http://127.0.0.1:8030/realtime
```

Backend endpoints:

```text
GET  /realtime
GET  /realtime/status
POST /realtime/uploads
WS   /ws/realtime
```

## Required environment

Do not commit real keys. Put them in `.env` only.

```bash
DEEPGRAM_API_KEY=dg_...
GROQ_API_KEY=gsk_...
```

`PROVIDER_DEEPGRAM_API_KEY`, `LIVE_DEEPGRAM_API_KEY`, `PROVIDER_GROQ_API_KEY`, and `LIVE_LLM_API_KEY` are also accepted as fallbacks.

The realtime Deepgram client needs the Python `websockets` package:

```bash
pip install websockets==14.1
```

## Recommended realtime defaults

```bash
LIVE_ENABLED=true
LIVE_DEEPGRAM_BASE_URL=wss://api.deepgram.com/v1/listen
LIVE_DEEPGRAM_MODEL=nova-3
LIVE_LANGUAGE=fa
LIVE_INTERIM_RESULTS=true
LIVE_PUNCTUATE=true
LIVE_SMART_FORMAT=true
LIVE_DIARIZE=false
LIVE_VAD_EVENTS=true
LIVE_ENDPOINTING_MS=700
LIVE_UTTERANCE_END_MS=1000
LIVE_DEEPGRAM_ENCODING=opus
LIVE_DEEPGRAM_SAMPLE_RATE=48000
LIVE_DEEPGRAM_CHANNELS=1
LIVE_DEEPGRAM_KEYTERMS=
LIVE_DEEPGRAM_KEYWORDS=
LIVE_DEEPGRAM_KEEPALIVE_SEC=5

LIVE_LLM_ENABLED=true
LIVE_LLM_PROVIDER=groq
LIVE_LLM_BASE_URL=https://api.groq.com/openai/v1
LIVE_LLM_MODEL=openai/gpt-oss-120b
LIVE_LLM_TEMPERATURE=0.1
LIVE_LLM_MAX_TOKENS=700
LIVE_LLM_TIMEOUT_SEC=25
LIVE_LLM_MIN_CHARS=220
LIVE_LLM_INTERVAL_SEC=18
LIVE_LLM_CONTEXT_CHARS=6000
LIVE_LLM_STRICT_SCHEMA=true
```

## Uploaded class file flow

The `/realtime` panel can now process a recorded class file as if it were being played live:

1. Select **فایل آپلودشده**.
2. Pick an audio/video file.
3. Click **آپلود فایل**.
4. Click **شروع**.

The backend uses the existing media pipeline to save the upload, extract audio with ffmpeg, probe duration with ffprobe, and store a temporary upload session. When playback starts, it streams raw `linear16` audio to Deepgram at realtime speed, so `transcript.partial`, `transcript.final`, and `teacher.hint` arrive progressively.

## WebSocket protocol

For microphone-style clients, the first client message should be JSON:

```json
{
  "type": "start",
  "source": "mic",
  "language": "fa",
  "topic": "calculus derivatives",
  "keyterms": "مشتق, حد, شیب",
  "diarize": false
}
```

Then send binary `audio/webm;codecs=opus` chunks. The server emits:

```text
session.started
stt.open
transcript.partial
transcript.final
teacher.hint
analysis.error
session.closed
```

For uploaded-file playback, first upload the file:

```text
POST /realtime/uploads
multipart/form-data: file=<audio-or-video>
```

Then open the websocket with:

```json
{
  "type": "start",
  "source": "upload",
  "upload_id": "<id from POST /realtime/uploads>",
  "language": "fa",
  "topic": "class topic",
  "keyterms": "term1, term2",
  "diarize": false
}
```

The server emits extra upload playback events:

```text
file.playback.started
file.playback.progress
file.playback.finished
```

`transcript.partial` is for UI captions. `transcript.final` is appended to the analysis buffer. `teacher.hint` contains the structured Groq JSON result for the teacher dashboard.
