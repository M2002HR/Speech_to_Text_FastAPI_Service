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

## Windows scripts

### Complete setup and start

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\setup_and_start_windows.ps1
```

If PowerShell blocks script execution, use a one-time bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_start_windows.ps1
```

### Complete setup and start for LAN

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_and_start_windows_lan.ps1
```

### Start only

```powershell
.\scripts\start_windows.ps1
```

`start_windows.ps1` does not install dependencies or run setup checks. It only starts the API from the existing `.venv`.

## Linux scripts

Make scripts executable once:

```bash
chmod +x scripts/setup_and_start_linux.sh scripts/setup_and_start_linux_lan.sh scripts/start_linux.sh
```

### Complete setup and start

```bash
./scripts/setup_and_start_linux.sh
```

### Complete setup and start for LAN

```bash
./scripts/setup_and_start_linux_lan.sh
```

### Start only

```bash
./scripts/start_linux.sh
```

`start_linux.sh` does not install dependencies or run setup checks. It only starts the API from the existing `.venv`.

Useful Linux setup flags:

```bash
./scripts/setup_and_start_linux.sh --no-start --skip-package-install --skip-tests --skip-smoke-tests
```

Override host/port:

```bash
./scripts/setup_and_start_linux.sh --host 0.0.0.0 --port 8030
./scripts/start_linux.sh --host 0.0.0.0 --port 8030
```

## Live accuracy settings

Recommended accuracy-oriented values are in:

```text
config/live_accuracy.env.example
```

Put real provider secrets only in your local `.env` and never commit them.

If a provider returns `403 Forbidden`, check model permissions in that provider project or organization.

If silence produces repeated text, keep VAD enabled in the UI. The browser VAD prevents silent chunks from reaching STT, and backend guards ignore prompt echo or no-speech hallucinations if they still happen.
