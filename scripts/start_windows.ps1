param(
  [string]$HostName = "0.0.0.0",
  [int]$Port = 0,
  [string]$Python = "",
  [switch]$NoPause
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log {
  param([string]$Tag, [string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Gray)
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host "[$stamp][$Tag] $Message" -ForegroundColor $Color
}

function Pause-BeforeExit {
  param([string]$Reason = "Script stopped")
  if ($NoPause -or $env:TOOTAK_NO_PAUSE -eq "1") { return }
  Write-Host ""
  Write-Host "$Reason. Press Enter to close this window..." -ForegroundColor Yellow
  try { [void](Read-Host) } catch { }
}

function Fail {
  param([string]$Message)
  Write-Log "ERROR" $Message Red
  throw $Message
}

function Import-DotEnv {
  param([string]$FilePath)
  if (-not (Test-Path $FilePath)) { return }
  Get-Content -Path $FilePath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) { return }
    $key = $parts[0].Trim()
    $value = $parts[1].Trim()
    if ($value.Length -ge 2) {
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }
    if (-not [Environment]::GetEnvironmentVariable($key, "Process")) {
      [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
  }
}

function Get-EnvValue {
  param([string]$Name, [string]$Default = "")
  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
  return $value
}

function Get-LocalIPv4Addresses {
  try {
    return @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
      Select-Object -ExpandProperty IPAddress -Unique)
  } catch {
    return @()
  }
}

$exitCode = 0
try {
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
  Set-Location $repoRoot

  if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $repoRoot
  } elseif (-not ($env:PYTHONPATH.Split(";") -contains $repoRoot)) {
    $env:PYTHONPATH = "$repoRoot;$env:PYTHONPATH"
  }

  Import-DotEnv -FilePath (Join-Path $repoRoot ".env")
  [Environment]::SetEnvironmentVariable("APP_CONFIG_FILE", (Get-EnvValue "APP_CONFIG_FILE" "config/config.yml"), "Process")

  $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if ([string]::IsNullOrWhiteSpace($Python)) {
    if (Test-Path $venvPython) {
      $Python = $venvPython
    } else {
      $cmd = Get-Command python -ErrorAction SilentlyContinue
      if ($cmd) { $Python = $cmd.Source }
    }
  }
  if ([string]::IsNullOrWhiteSpace($Python) -or -not (Test-Path $Python)) {
    Fail "Python was not found. Run .\scripts\setup_and_start_windows.ps1 once first, or pass -Python <path>."
  }

  $finalPort = if ($Port -gt 0) { $Port } else { [int](Get-EnvValue "APP_PORT" "8030") }
  $env:APP_HOST = $HostName
  $env:APP_PORT = [string]$finalPort

  Write-Log "OK" "Starting Tootak without setup checks." Green
  Write-Log "INFO" "Bind: http://$HostName`:$finalPort" Cyan
  Write-Log "INFO" "Local: http://127.0.0.1`:$finalPort" Cyan
  foreach ($ip in Get-LocalIPv4Addresses) {
    Write-Log "INFO" "LAN:   http://$ip`:$finalPort" Cyan
  }
  Write-Log "INFO" "Live:  http://127.0.0.1`:$finalPort/live" Cyan
  Write-Log "INFO" "Press Ctrl+C to stop." Gray

  & $Python -m uvicorn api.app.main:app --host $HostName --port $finalPort --reload
  $exitCode = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } else { 0 }
  if ($exitCode -ne 0) {
    Write-Log "FAILED" "uvicorn exited with code $exitCode" Red
  } else {
    Write-Log "STOPPED" "uvicorn stopped." Yellow
  }
} catch {
  $exitCode = 1
  Write-Log "FAILED" $_.Exception.Message Red
} finally {
  if ($exitCode -ne 0) {
    Pause-BeforeExit -Reason "Script failed"
  } else {
    Pause-BeforeExit -Reason "Server stopped"
  }
}
exit $exitCode
