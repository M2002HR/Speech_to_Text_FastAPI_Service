param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Pause-BeforeExit {
  param([string]$Reason = "Script stopped")
  if ($env:TOOTAK_NO_PAUSE -eq "1") { return }
  Write-Host ""
  Write-Host "$Reason. Press Enter to close this window..." -ForegroundColor Yellow
  try { [void](Read-Host) } catch { }
}

$exitCode = 0
try {
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $setupScript = Join-Path $scriptDir "setup_and_start_windows.ps1"
  $startScript = Join-Path $scriptDir "start_windows.ps1"
  if (-not (Test-Path $setupScript)) {
    throw "setup_and_start_windows.ps1 was not found next to this script."
  }
  if (-not (Test-Path $startScript)) {
    throw "start_windows.ps1 was not found next to this script."
  }

  Write-Host "Running full Windows setup checks with LAN bind host 0.0.0.0..." -ForegroundColor Cyan
  & $setupScript -HostName "0.0.0.0" -NoStart @Args
  $exitCode = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } else { 0 }
  if ($exitCode -ne 0) {
    Write-Host "setup_and_start_windows.ps1 exited with code $exitCode" -ForegroundColor Red
  } else {
    Write-Host "Starting live-enabled app entrypoint..." -ForegroundColor Cyan
    & $startScript -HostName "0.0.0.0"
    $exitCode = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } else { 0 }
  }
} catch {
  $exitCode = 1
  Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
} finally {
  if ($exitCode -ne 0) {
    Pause-BeforeExit -Reason "Script failed"
  }
}
exit $exitCode
