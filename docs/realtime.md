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
GET /realtime
GET /realtime/status
WS  /ws/realtime
```

## Required environment

Do not commit real keys. Put them in `.env` only.

```bash
DEEPGRAM_API_KEY=dg_...
GROQ_API_KEY=gsk_...
```

`PROVIDER_DEEPGRAM_API_KEY`, `LIVE_DEEPGRAM_API_KEY`, `PROVIDER_GROQ_API_KEY`, and `LIVE_LLM_API_KEY` are also accepted as fallbacks.

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

## WebSocket protocol

The first client message should be JSON:

```json
{
  "type": "start",
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

`transcript.partial` is for UI captions. `transcript.final` is appended to the analysis buffer. `teacher.hint` contains the structured Groq JSON result for the teacher dashboard.
