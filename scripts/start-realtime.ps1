param(
    [int]$Port = 8030,
    [string]$HostAddress = "0.0.0.0",
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Tootak realtime startup" -ForegroundColor Cyan
Write-Host "Project: $Root"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    py -3 -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python executable was not found in .venv. Delete .venv and run this script again."
}

if (-not $NoInstall) {
    Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements.txt
    & $Python -m pip install websockets==14.1
}

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

$EnvText = Get-Content ".env" -Raw
if ($EnvText -notmatch "(?m)^DEEPGRAM_API_KEY=.+") {
    Write-Host "WARNING: Set DEEPGRAM_API_KEY in .env before using realtime STT." -ForegroundColor Red
}
if ($EnvText -notmatch "(?m)^(GROQ_API_KEY|PROVIDER_GROQ_API_KEY|LIVE_LLM_API_KEY)=.+") {
    Write-Host "WARNING: Set GROQ_API_KEY in .env if you want teacher feedback from Groq." -ForegroundColor Yellow
}

$env:APP_HOST = $HostAddress
$env:APP_PORT = [string]$Port

Write-Host "Starting realtime server..." -ForegroundColor Green
Write-Host "Open: http://127.0.0.1:$Port/realtime" -ForegroundColor Green

& $Python -m uvicorn api.app.asgi:app --host $HostAddress --port $Port --reload
