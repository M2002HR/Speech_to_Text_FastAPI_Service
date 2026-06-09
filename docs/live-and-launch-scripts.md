# Live mode and launch scripts

## Live transcription at `/live`

The live panel is designed for classroom-style Persian transcription.

Main behavior:

- The browser records microphone audio.
- Browser-side VAD checks whether there is meaningful sound before sending a chunk.
- Silent or low-energy chunks are skipped in the browser and are not sent to STT.
- Each sent chunk is a standalone MediaRecorder file so STT providers can process it as a valid media file.
- The backend still has runtime guards for no-speech chunks, prompt echo, repeated hallucinations, provider errors, and safer LLM cleanup.
- Optional audio/class topic is sent as context to STT and LLM cleanup.
- LLM cleanup uses previous transcript context and should not repeat previous text.

Open:

```text
http://127.0.0.1:8030/live
```

For LAN usage, open the LAN address printed by the launcher, for example:

```text
http://192.168.1.23:8030/live
```

## Launch scripts

There is exactly one launcher per platform. Each one installs all
dependencies and starts the full service in a single run, serving the
transcription API plus `/live` and `/realtime` via `api.app.server:app`.

- Linux/macOS: `scripts/start.sh`
- Windows PowerShell: `scripts/start.ps1`
- Windows CMD: `scripts/start.cmd` (forwards all arguments to `start.ps1`)

Every behavior is configurable through arguments; nothing else is needed.

## Windows

### Complete setup and start (binds 0.0.0.0 for LAN by default)

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\start.ps1
```

If PowerShell blocks script execution, use a one-time bypass (or run `start.cmd`):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

### Bind to localhost only

```powershell
.\scripts\start.ps1 -Local
```

### Setup only, no server

```powershell
.\scripts\start.ps1 -NoStart
```

Other flags: `-Port <n>`, `-LocalModelId small`, `-NoReload`,
`-EnvVars "KEY=VALUE","KEY2=VALUE2"`, and the `-Skip*` flags.

## Linux/macOS

Make the script executable once:

```bash
chmod +x scripts/start.sh
```

### Complete setup and start (binds 0.0.0.0 for LAN by default)

```bash
./scripts/start.sh
```

### Bind to localhost only

```bash
./scripts/start.sh --local
```

### Setup only, no server

```bash
./scripts/start.sh --no-start --skip-package-install --skip-tests --skip-smoke-tests
```

### Override host/port and pass extra env vars

```bash
./scripts/start.sh --host 0.0.0.0 --port 8030
./scripts/start.sh -e DEEPGRAM_API_KEY=xxx -e LIVE_LANGUAGE=en
```

Run `./scripts/start.sh --help` for the full option list.

## Live accuracy settings

Recommended accuracy-oriented values are in:

```text
config/live_accuracy.env.example
```

Put real provider secrets only in your local `.env` and never commit them.

If a provider returns `403 Forbidden`, check model permissions in that provider project or organization.

If silence produces repeated text, keep VAD enabled in the UI. The browser VAD prevents silent chunks from reaching STT, and backend guards ignore prompt echo or no-speech hallucinations if they still happen.
