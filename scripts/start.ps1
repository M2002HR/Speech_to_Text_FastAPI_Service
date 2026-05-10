$envFile = if ($env:ENV_FILE) { $env:ENV_FILE } else { '.env' }
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $parts = $_ -split '=', 2
    if ($parts.Count -eq 2) {
      [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
    }
  }
}

$hostValue = if ($env:APP_HOST) { $env:APP_HOST } else { '0.0.0.0' }
$portValue = if ($env:APP_PORT) { $env:APP_PORT } else { '8000' }

python -m uvicorn api.app.main:app --host $hostValue --port $portValue --reload
