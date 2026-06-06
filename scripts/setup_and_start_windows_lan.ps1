param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$setupScript = Join-Path $scriptDir "setup_and_start_windows.ps1"
if (-not (Test-Path $setupScript)) {
  throw "setup_and_start_windows.ps1 was not found next to this script."
}

Write-Host "Starting full Windows setup with LAN bind host 0.0.0.0..." -ForegroundColor Cyan
& $setupScript -HostName "0.0.0.0" @Args
exit $LASTEXITCODE
