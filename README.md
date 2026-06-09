# Tootak (FastAPI)

A production-oriented FastAPI service that converts audio/video files to text.

Features:
- Upload audio or video files
- Automatic video-to-audio extraction via ffmpeg
- Local transcription backend (`faster-whisper`)
- API-based transcription backends (OpenAI-compatible: OpenAI / Groq / Custom)
- Model download job system (create/list/status/cancel)
- Hugging Face API integration for model discovery and downloads
- Fully configurable via `config.yml` + `.env`
- Two built-in web UIs:
  - User panel at `/` (simple ultra-stable transcription flow)
  - Lab panel at `/lab` (full settings, model management, download jobs)
- Swagger/OpenAPI docs and test suite

## Project Structure

- `api/app/main.py`: FastAPI routes and app bootstrap
- `api/app/config.py`: configuration loader (`env > config.yml > defaults`)
- `api/app/services.py`: media processing, transcription, download jobs
- `api/app/schemas.py`: request/response schemas
- `config/config.example.yml`: example YAML config
- `.env.example`: complete environment variable reference
- `tests/`: API/config/service tests
- `scripts/start.sh`: single Linux/macOS launcher (installs everything + starts all services)
- `scripts/start.ps1`: single Windows PowerShell launcher (installs everything + starts all services)
- `scripts/start.cmd`: single Windows CMD launcher (forwards to `start.ps1`)

## Prerequisites

- Python 3.10+
- ffmpeg + ffprobe available in PATH

## Install ffmpeg

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y ffmpeg
```

### Windows

1. Install ffmpeg (e.g., via `winget` or manual zip).
2. Ensure `ffmpeg` and `ffprobe` are available in your PATH.

Example with winget:

```powershell
winget install --id Gyan.FFmpeg -e
```

## Setup

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/config.example.yml config/config.yml
```

### Windows (PowerShell)

Full first-run setup without Docker — installs everything and starts the full
service (transcription API + `/live` + `/realtime`):

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\start.ps1
```

From `cmd.exe` you can run `scripts\start.cmd` with the same arguments.

Setup only, without starting the foreground server:

```powershell
.\scripts\start.ps1 -NoStart
```

The script creates `.venv`, installs Python packages, creates `.env` and
`config/config.yml` when missing, installs or downloads ffmpeg/ffprobe when
needed, guides Hugging Face token setup when local model download is enabled,
validates configured OpenAI/Groq keys when present, runs tests, starts a
temporary server for smoke checks, and then starts the service in foreground
unless `-NoStart` is used. It binds `0.0.0.0` (LAN) by default; use `-Local`
for `127.0.0.1` only.

Useful flags:

```powershell
.\scripts\start.ps1 -NoStart -SkipPackageInstall -SkipLocalModelDownload -SkipHfTokenPrompt -SkipTests -SkipApiKeyValidation -SkipSmokeTests -NoReload
.\scripts\start.ps1 -Local -Port 9000 -LocalModelId small
.\scripts\start.ps1 -EnvVars "DEEPGRAM_API_KEY=hf_xxx","LIVE_LANGUAGE=en"
```

If you want higher Hugging Face download limits, create a read token at
`https://huggingface.co/settings/tokens` and either paste it when prompted or pass:

```powershell
.\scripts\start.ps1 -HfToken "hf_..."
```

To set up the environment manually instead of using the launcher:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item config\config.example.yml config\config.yml
```

## Run the Service

The unified ASGI app `api.app.server:app` serves every feature in one process:
the transcription API and web panels (`/`, `/lab`), the `/live` websocket, and
the `/realtime` streaming panel.

### Linux/macOS

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

`start.sh` installs everything and starts the service. Common options:

```bash
./scripts/start.sh --local --port 9000              # bind 127.0.0.1 only
./scripts/start.sh --no-start --skip-tests          # setup + checks, no server
./scripts/start.sh -e DEEPGRAM_API_KEY=xxx          # pass extra env vars
./scripts/start.sh --help                           # full option list
```

To run uvicorn directly against an already-prepared `.venv`:

```bash
uvicorn api.app.server:app --host 0.0.0.0 --port 8030 --reload
```

### Windows (PowerShell)

```powershell
.\scripts\start.ps1
```

To run uvicorn directly against an already-prepared `.venv`:

```powershell
python -m uvicorn api.app.server:app --host 0.0.0.0 --port 8030 --reload
```

## API Docs

- Web UI: `http://127.0.0.1:8030/`
- Swagger UI: `http://127.0.0.1:8030/docs`
- ReDoc: `http://127.0.0.1:8030/redoc`

## Core Endpoints

- `GET /health`
- `GET /providers`
- `POST /transcribe`
- `POST /transcribe/jobs`
- `GET /transcribe/jobs`
- `GET /transcribe/jobs/{job_id}`
- `POST /transcribe/jobs/{job_id}/retry`

For Groq/OpenAI fallback keys, keep the primary key in `PROVIDER_GROQ_API_KEY`
or `PROVIDER_OPENAI_API_KEY` and put additional comma-separated keys in
`PROVIDER_GROQ_API_KEYS` or `PROVIDER_OPENAI_API_KEYS`. Retryable upstream
errors such as rate limits rotate to the next configured key. Failed chunked
API jobs keep checkpoint state under `runtime/checkpoints/` so retry can resume
from completed chunks.

## Admin Endpoints

- `GET /admin/system/config-effective`
- `GET /admin/models/presets`
- `GET /admin/models/local`
- `GET /admin/models/remote/repos`
- `GET /admin/models/remote/files`
- `POST /admin/models/local/download`
- `POST /admin/models/url/huggingface-file`
- `POST /admin/downloads`
- `GET /admin/downloads`
- `GET /admin/downloads/{job_id}`
- `POST /admin/downloads/{job_id}/cancel`

## Transcription Example

### Linux/macOS

```bash
curl -X POST http://127.0.0.1:8030/transcribe \
  -F "file=@sample.mp4" \
  -F "provider=local" \
  -F "model=small" \
  -F "language=fa"
```

### Windows (PowerShell with `curl.exe`)

```powershell
curl.exe -X POST http://127.0.0.1:8030/transcribe `
  -F "file=@sample.mp4" `
  -F "provider=local" `
  -F "model=small" `
  -F "language=fa"
```

## Manual Model Download (Recommended)

If you want to download models manually and use them in the app, place each model in its own directory under:

- `runtime/models/<model-folder>/`

Minimum required files for local `faster-whisper` usage:

- `config.json`
- `model.bin`
- `tokenizer.json` (or `tokenizer_config.json`)
- `vocabulary.json` or `vocabulary.txt`

Example:

```text
runtime/models/faster-whisper-small/
  config.json
  model.bin
  tokenizer.json
  vocabulary.txt
```

After placing files:

1. Restart the API service.
2. Open `GET /admin/models/local` (or the UI models section) to verify detection.
3. Set `provider=local` and `model` to either:
   - absolute model path, or
   - model alias (for example `small`, `medium`, `large-v3`) when mapped to a local folder.

## Tests

### Linux/macOS

```bash
pytest -q
```

### Windows (PowerShell)

```powershell
pytest -q
```

## Configuration Priority

The service loads config in this order:

1. defaults in code
2. `config/config.yml`
3. environment variables (`.env` / process env)

Final precedence: `env > config.yml > defaults`

## Important Behavior

- No model is downloaded automatically unless you explicitly create a download job.
- Download endpoints are job-based and track progress/status.
- Async transcription jobs are available and expose progress percent/status for UI polling.
- Local transcription requires `faster-whisper` runtime dependencies if you enable local processing in production.
