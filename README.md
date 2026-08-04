# Tootak — Speech-to-Text FastAPI Service

**A configurable speech-to-text platform for audio and video, with local and API-based transcription backends.**

Tootak combines FastAPI, FFmpeg, faster-whisper, background jobs, model management, and built-in web interfaces in one service. It supports local inference as well as OpenAI-compatible providers such as OpenAI, Groq, or a custom endpoint.

## Engineering highlights

- Audio and video upload with automatic FFmpeg extraction
- Local transcription through `faster-whisper`
- OpenAI-compatible remote transcription providers
- Background transcription and model-download jobs
- Retryable chunked jobs with checkpoint recovery
- Hugging Face model discovery and downloads
- REST API, Swagger/OpenAPI, user UI, lab UI, and real-time interfaces
- Cross-platform launch scripts for Linux, macOS, and Windows
- Config precedence through environment variables, YAML, and defaults
- Test suite covering API, configuration, and service behavior

## Technology

`Python` · `FastAPI` · `Pydantic` · `faster-whisper` · `FFmpeg` · `Hugging Face` · `WebSocket` · `OpenAPI` · `pytest`

## Architecture

```text
Client / Web UI
  │
  ▼
FastAPI application
  ├── upload validation
  ├── media extraction with FFmpeg
  ├── synchronous or background jobs
  ├── model management
  └── provider selection
        │
        ├── Local faster-whisper models
        └── OpenAI-compatible transcription APIs
```

## Main capabilities

| Area | Capability |
| --- | --- |
| Media | Audio and video input, FFmpeg extraction |
| Local AI | faster-whisper inference |
| Remote AI | OpenAI, Groq, or custom compatible APIs |
| Jobs | Create, list, inspect, retry, and cancel jobs |
| Models | Discover and download Hugging Face models |
| Interfaces | User panel, lab panel, Swagger, ReDoc, WebSocket |
| Reliability | Key rotation, chunk checkpoints, retry support |

## Quick start

### Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available in `PATH`

### Linux or macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/config.example.yml config/config.yml
chmod +x scripts/start.sh
./scripts/start.sh
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\start.ps1
```

The launchers can prepare the environment, install dependencies, validate configuration, run tests and smoke checks, and start the service.

## Local interfaces

- User UI: `http://127.0.0.1:8030/`
- Lab UI: `http://127.0.0.1:8030/lab`
- Swagger: `http://127.0.0.1:8030/docs`
- ReDoc: `http://127.0.0.1:8030/redoc`
- Realtime UI: `http://127.0.0.1:8030/realtime`

## Core API

```text
GET  /health
GET  /providers
POST /transcribe
POST /transcribe/jobs
GET  /transcribe/jobs
GET  /transcribe/jobs/{job_id}
POST /transcribe/jobs/{job_id}/retry
```

### Example transcription

```bash
curl -X POST http://127.0.0.1:8030/transcribe \
  -F 'file=@sample.mp4' \
  -F 'provider=local' \
  -F 'model=small' \
  -F 'language=fa'
```

## Model administration

The admin API supports:

- effective configuration inspection
- model presets and local model inventory
- Hugging Face repository and file discovery
- background model downloads
- download status and cancellation

Local faster-whisper models can be placed under:

```text
runtime/models/<model-folder>/
```

## Configuration

Configuration precedence is:

```text
environment variables > config.yml > application defaults
```

Use `.env.example` and `config/config.example.yml` as the configuration contracts.

Provider fallback keys can be configured as comma-separated values. Retryable upstream errors rotate through available keys. Chunked remote jobs persist checkpoints under `runtime/checkpoints/` so retries can continue from completed work.

## Repository structure

```text
api/app/
  server.py       # unified ASGI application
  main.py         # API routes and application setup
  config.py       # configuration loader
  services.py     # media, transcription, and download services
  schemas.py      # request and response models
config/
scripts/
tests/
runtime/
```

## Development verification

```bash
pytest -q
uvicorn api.app.server:app --host 127.0.0.1 --port 8030 --reload
```

For manual verification, test at least one audio file, one video file, one local model, one remote provider, job retry behavior, and model-download cancellation.

## Security and operational notes

- Keep API keys, Hugging Face tokens, and runtime configuration out of Git.
- Restrict file size, content type, and processing duration in exposed deployments.
- Run FFmpeg and model processing with resource limits.
- Protect administration and model-download endpoints.
- Treat uploaded media, transcripts, and checkpoints as sensitive data.

## Project status

Tootak demonstrates AI-service integration, media processing, FastAPI backend design, background-job workflows, model lifecycle management, and cross-platform developer tooling.