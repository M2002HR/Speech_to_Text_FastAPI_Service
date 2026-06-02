param(
  [switch]$NoStart,
  [switch]$SetupOnly,
  [switch]$SkipPackageInstall,
  [switch]$SkipTests,
  [switch]$SkipApiKeyValidation,
  [switch]$SkipSmokeTests,
  [switch]$SkipFFmpegInstall,
  [switch]$SkipLocalModelDownload,
  [switch]$SkipHfTokenPrompt,
  [switch]$RequireLocalModel,
  [switch]$FailOnInvalidApiKey,
  [switch]$NonInteractive,
  [string]$Python = "",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 0,
  [string]$LocalModelId = "tiny",
  [string]$HfToken = "",
  [int]$StartupTimeoutSec = 120,
  [int]$SmokeTimeoutSec = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:StageIndex = 0
$script:StageTotal = 12
$script:CreatedEnvFile = $false
$script:LocalModelReady = $false
$script:LocalModelSkippedByUser = $false

function Write-Log {
  param(
    [string]$Tag,
    [string]$Message,
    [ConsoleColor]$Color = [ConsoleColor]::Gray
  )
  $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host "[$stamp][$Tag] $Message" -ForegroundColor $Color
}

function Write-Stage {
  param([string]$Message)
  $script:StageIndex += 1
  Write-Log "STAGE $script:StageIndex/$script:StageTotal" $Message Cyan
}

function Write-Info {
  param([string]$Message)
  Write-Log "INFO" $Message Gray
}

function Write-Warn {
  param([string]$Message)
  Write-Log "WARN" $Message Yellow
}

function Write-Ok {
  param([string]$Message)
  Write-Log "OK" $Message Green
}

function Write-StepDetail {
  param([string]$Message)
  Write-Log "DETAIL" $Message DarkGray
}

function Fail {
  param([string]$Message)
  Write-Log "ERROR" $Message Red
  throw $Message
}

function Write-BootstrapHelp {
  Write-Log "HELP" "Optional skip flags: -SkipPackageInstall, -SkipLocalModelDownload, -SkipHfTokenPrompt, -SkipTests, -SkipApiKeyValidation, -SkipSmokeTests, -SkipFFmpegInstall, -NoStart" DarkCyan
  Write-Log "HELP" "Useful modes: -NoStart for setup+tests only, -NonInteractive for unattended runs, -LocalModelId tiny|small|medium|large-v3" DarkCyan
}

function Invoke-Native {
  param(
    [string]$Label,
    [string]$FilePath,
    [string[]]$Arguments
  )
  Write-Info $Label
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    Fail "$Label failed with exit code $LASTEXITCODE"
  }
}

function Convert-ToEnvPath {
  param([string]$PathValue)
  return $PathValue.Replace("\", "/")
}

function Get-EnvValue {
  param(
    [string]$Name,
    [string]$Default = ""
  )
  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $Default
  }
  return $value
}

function Set-EnvFileValue {
  param(
    [string]$FilePath,
    [string]$Key,
    [string]$Value
  )
  $line = "$Key=$Value"
  if (-not (Test-Path $FilePath)) {
    Set-Content -Path $FilePath -Value $line -Encoding UTF8
    return
  }

  $lines = @(Get-Content -Path $FilePath)
  $found = $false
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "^\s*$([regex]::Escape($Key))\s*=") {
      $lines[$i] = $line
      $found = $true
      break
    }
  }
  if (-not $found) {
    $lines += $line
  }
  Set-Content -Path $FilePath -Value $lines -Encoding UTF8
}

function Get-EnvFileValue {
  param(
    [string]$FilePath,
    [string]$Key
  )
  if (-not (Test-Path $FilePath)) {
    return ""
  }
  foreach ($line in Get-Content -Path $FilePath) {
    if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
      return (($line -split "=", 2)[1]).Trim()
    }
  }
  return ""
}

function Migrate-DefaultPort {
  param([string]$EnvFile)
  $currentPort = Get-EnvFileValue -FilePath $EnvFile -Key "APP_PORT"
  if ([string]::IsNullOrWhiteSpace($currentPort) -or $currentPort -eq "8000") {
    Set-EnvFileValue -FilePath $EnvFile -Key "APP_PORT" -Value "8030"
    Write-Ok "APP_PORT default set to 8030."
  } else {
    Write-Ok "APP_PORT is already customized: $currentPort"
  }

  $localSttUrl = Get-EnvFileValue -FilePath $EnvFile -Key "LOCAL_STT_URL"
  if ([string]::IsNullOrWhiteSpace($localSttUrl) -or $localSttUrl -eq "http://127.0.0.1:8000/transcribe") {
    Set-EnvFileValue -FilePath $EnvFile -Key "LOCAL_STT_URL" -Value "http://127.0.0.1:8030/transcribe"
  }

  $localSttJobsUrl = Get-EnvFileValue -FilePath $EnvFile -Key "LOCAL_STT_JOBS_URL"
  if ([string]::IsNullOrWhiteSpace($localSttJobsUrl) -or $localSttJobsUrl -eq "http://127.0.0.1:8000/transcribe/jobs") {
    Set-EnvFileValue -FilePath $EnvFile -Key "LOCAL_STT_JOBS_URL" -Value "http://127.0.0.1:8030/transcribe/jobs"
  }
}

function Import-DotEnv {
  param([string]$FilePath)
  if (-not (Test-Path $FilePath)) {
    return
  }

  Get-Content -Path $FilePath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
      return
    }
    $parts = $line -split "=", 2
    if ($parts.Count -ne 2) {
      return
    }
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

function Get-HfTokenFromEnvironment {
  foreach ($name in @("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN")) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value)) {
      return [string]$value
    }
  }
  return ""
}

function Set-HfTokenForProcess {
  param([string]$Token)
  if ([string]::IsNullOrWhiteSpace($Token)) {
    return
  }
  [Environment]::SetEnvironmentVariable("HF_TOKEN", $Token.Trim(), "Process")
  [Environment]::SetEnvironmentVariable("HUGGINGFACE_HUB_TOKEN", $Token.Trim(), "Process")
}

function Prepare-HuggingFaceAccess {
  param(
    [string]$EnvFile,
    [string]$ProvidedToken
  )

  [Environment]::SetEnvironmentVariable("HF_HUB_DISABLE_SYMLINKS_WARNING", "1", "Process")
  Set-EnvFileValue -FilePath $EnvFile -Key "HF_HUB_DISABLE_SYMLINKS_WARNING" -Value "1"

  if (-not [string]::IsNullOrWhiteSpace($ProvidedToken)) {
    Set-HfTokenForProcess -Token $ProvidedToken
    Set-EnvFileValue -FilePath $EnvFile -Key "HF_TOKEN" -Value $ProvidedToken.Trim()
    Write-Ok "HuggingFace token was provided via -HfToken and saved to .env."
    return "token"
  }

  $existingToken = Get-HfTokenFromEnvironment
  if (-not [string]::IsNullOrWhiteSpace($existingToken)) {
    Set-HfTokenForProcess -Token $existingToken
    Write-Ok "HuggingFace token found in environment/.env: $(Mask-Secret $existingToken)"
    return "token"
  }

  Write-Warn "HuggingFace token is not configured. Public model downloads usually work without it, but may be slower or rate-limited."
  Write-Info "Create a token here: https://huggingface.co/settings/tokens"
  Write-StepDetail "Recommended token type: Read access. You can continue without a token or skip local model download."

  if ($NonInteractive -or $SkipHfTokenPrompt) {
    Write-Warn "Continuing without HuggingFace token because prompt is disabled."
    return "anonymous"
  }

  while ($true) {
    Write-Host ""
    Write-Host "HuggingFace options:" -ForegroundColor Cyan
    Write-Host "  1) Paste token and save to .env"
    Write-Host "  2) Continue without token"
    Write-Host "  3) Skip local model download"
    Write-Host "  4) Open token page in browser"
    $choice = Read-Host "Choose 1/2/3/4 (default: 2)"
    if ([string]::IsNullOrWhiteSpace($choice)) {
      $choice = "2"
    }

    switch ($choice.Trim()) {
      "1" {
        $token = Read-Host "Paste HF token"
        if ([string]::IsNullOrWhiteSpace($token)) {
          Write-Warn "Empty token ignored."
          continue
        }
        Set-HfTokenForProcess -Token $token
        Set-EnvFileValue -FilePath $EnvFile -Key "HF_TOKEN" -Value $token.Trim()
        Write-Ok "HuggingFace token saved to .env."
        return "token"
      }
      "2" {
        Write-Warn "Continuing without HuggingFace token."
        return "anonymous"
      }
      "3" {
        Write-Warn "Local model download was skipped by user."
        $script:LocalModelSkippedByUser = $true
        return "skip-model"
      }
      "4" {
        Start-Process "https://huggingface.co/settings/tokens"
        Write-Info "Token page opened. Create a Read token, then choose option 1 and paste it."
        continue
      }
      default {
        Write-Warn "Invalid choice. Choose 1, 2, 3, or 4."
      }
    }
  }
}

function Test-CommandAvailable {
  param([string]$CommandName)
  return $null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-BinaryAvailable {
  param([string]$Binary)
  if ([string]::IsNullOrWhiteSpace($Binary)) {
    return $false
  }
  if ($Binary -match "[\\/]" -or $Binary.EndsWith(".exe")) {
    return Test-Path $Binary
  }
  return Test-CommandAvailable $Binary
}

function Refresh-ProcessPath {
  $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:Path = "$machinePath;$userPath;$env:Path"
}

function Find-InstalledPythonExecutables {
  $paths = @()

  $localPythonRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Programs\Python" } else { "" }
  foreach ($root in @($localPythonRoot, $env:ProgramFiles, ${env:ProgramFiles(x86)})) {
    if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path $root)) {
      continue
    }
    $paths += Get-ChildItem -Path $root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
      ForEach-Object { Join-Path $_.FullName "python.exe" } |
      Where-Object { Test-Path $_ }
  }
  return @($paths | Select-Object -Unique)
}

function Install-PythonAutomatically {
  param([string]$RepoRoot)

  if (Test-CommandAvailable "winget") {
    Write-Info "Python 3.10+ was not found. Trying winget install for Python.Python.3.11"
    & winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements --silent 2>&1 |
      ForEach-Object {
        $line = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($line)) {
          Write-Info $line
        }
      }
    Refresh-ProcessPath
    if ($LASTEXITCODE -eq 0) {
      Write-Ok "Python installed with winget."
      return [bool]$true
    }
    Write-Warn "winget Python installation failed with exit code $LASTEXITCODE"
  } else {
    Write-Warn "winget is not available; direct Python installer download will be used."
  }

  $toolsDir = Join-Path $RepoRoot ".tools"
  New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
  $installerPath = Join-Path $toolsDir "python-3.11.9-amd64.exe"
  $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

  Write-Info "Downloading Python installer from $pythonUrl"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
  Write-Info "Installing Python silently for current user"
  $proc = Start-Process -FilePath $installerPath `
    -ArgumentList @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_launcher=1") `
    -Wait `
    -PassThru
  Refresh-ProcessPath
  if ($proc.ExitCode -eq 0) {
    Write-Ok "Python installer completed."
    return [bool]$true
  }

  Write-Warn "Python installer exited with code $($proc.ExitCode)"
  return [bool]$false
}

function Resolve-PythonExecutable {
  param(
    [string]$PreferredPython,
    [string]$RepoRoot,
    [bool]$AllowAutoInstall = $true
  )

  $code = "import json, sys; print(json.dumps({'executable': sys.executable, 'version': list(sys.version_info[:3]), 'ok': sys.version_info >= (3, 10)}))"
  $candidates = @()
  if (-not [string]::IsNullOrWhiteSpace($PreferredPython)) {
    $candidates += @{ File = $PreferredPython; Args = @() }
  }
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) {
    $candidates += @{ File = $pythonCommand.Source; Args = @() }
  }
  $python3Command = Get-Command python3 -ErrorAction SilentlyContinue
  if ($python3Command) {
    $candidates += @{ File = $python3Command.Source; Args = @() }
  }
  $pyCommand = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCommand) {
    $candidates += @{ File = $pyCommand.Source; Args = @("-3") }
  }
  foreach ($installedPython in Find-InstalledPythonExecutables) {
    $candidates += @{ File = $installedPython; Args = @() }
  }

  foreach ($candidate in $candidates) {
    try {
      $out = & $candidate.File @($candidate.Args) -c $code 2>$null
      if (-not $out) {
        continue
      }
      $payload = $out | Select-Object -Last 1 | ConvertFrom-Json
      if ($payload.ok -eq $true) {
        $version = ($payload.version -join ".")
        Write-Ok "Python $version found: $($payload.executable)"
        return [string]$payload.executable
      }
      Write-Warn "Ignoring Python below 3.10: $($payload.executable)"
    } catch {
      continue
    }
  }

  if ($AllowAutoInstall -and (Install-PythonAutomatically -RepoRoot $RepoRoot)) {
    return Resolve-PythonExecutable -PreferredPython $PreferredPython -RepoRoot $RepoRoot -AllowAutoInstall $false
  }

  Fail "Python 3.10+ could not be installed automatically. Install Python 3.10+ or rerun with -Python <path>."
}

function Install-FFmpegWithWinget {
  if (-not (Test-CommandAvailable "winget")) {
    Write-Warn "winget is not available; manual ffmpeg download will be used."
    return $false
  }

  $ids = @("Gyan.FFmpeg.Essentials", "Gyan.FFmpeg")
  foreach ($id in $ids) {
    Write-Info "Trying winget install for $id"
    & winget install --id $id -e --accept-package-agreements --accept-source-agreements --silent 2>&1 |
      ForEach-Object {
        $line = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($line)) {
          Write-Info $line
        }
      }
    if ($LASTEXITCODE -eq 0) {
      Refresh-ProcessPath
      if ((Test-BinaryAvailable "ffmpeg") -and (Test-BinaryAvailable "ffprobe")) {
        Write-Ok "ffmpeg installed with winget package $id"
        return [bool]$true
      }
      Write-Warn "winget installed $id, but ffmpeg is still not visible in PATH."
    } else {
      Write-Warn "winget package $id failed with exit code $LASTEXITCODE"
    }
  }

  return [bool]$false
}

function Install-FFmpegManually {
  param(
    [string]$RepoRoot,
    [string]$EnvFile
  )

  $toolsDir = Join-Path $RepoRoot ".tools"
  $ffmpegDir = Join-Path $toolsDir "ffmpeg"
  $zipPath = Join-Path $toolsDir "ffmpeg-release-essentials.zip"
  New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

  $ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
  Write-Info "Downloading ffmpeg essentials from $ffmpegUrl"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $ffmpegUrl -OutFile $zipPath -UseBasicParsing

  if (Test-Path $ffmpegDir) {
    $resolvedRepo = (Resolve-Path $RepoRoot).Path
    $resolvedTarget = (Resolve-Path $ffmpegDir).Path
    if (-not $resolvedTarget.StartsWith($resolvedRepo, [StringComparison]::OrdinalIgnoreCase)) {
      Fail "Refusing to remove ffmpeg directory outside repository: $resolvedTarget"
    }
    Remove-Item -LiteralPath $ffmpegDir -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
  Write-Info "Extracting ffmpeg into $ffmpegDir"
  Expand-Archive -Path $zipPath -DestinationPath $ffmpegDir -Force

  $ffmpegExe = Get-ChildItem -Path $ffmpegDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
  $ffprobeExe = Get-ChildItem -Path $ffmpegDir -Recurse -Filter ffprobe.exe | Select-Object -First 1
  if (-not $ffmpegExe -or -not $ffprobeExe) {
    Fail "Downloaded ffmpeg archive does not contain ffmpeg.exe and ffprobe.exe"
  }

  $env:Path = "$($ffmpegExe.DirectoryName);$env:Path"
  $ffmpegPath = Convert-ToEnvPath $ffmpegExe.FullName
  $ffprobePath = Convert-ToEnvPath $ffprobeExe.FullName
  Set-EnvFileValue -FilePath $EnvFile -Key "PROCESSING_FFMPEG_BINARY" -Value $ffmpegPath
  Set-EnvFileValue -FilePath $EnvFile -Key "PROCESSING_FFPROBE_BINARY" -Value $ffprobePath
  [Environment]::SetEnvironmentVariable("PROCESSING_FFMPEG_BINARY", $ffmpegPath, "Process")
  [Environment]::SetEnvironmentVariable("PROCESSING_FFPROBE_BINARY", $ffprobePath, "Process")
  Write-Ok "ffmpeg prepared locally: $ffmpegPath"
  return $true
}

function Test-FFmpeg {
  param(
    [string]$FfmpegBinary,
    [string]$FfprobeBinary,
    [string]$AudioPath
  )

  Write-Info "Testing ffmpeg binary: $FfmpegBinary"
  & $FfmpegBinary -version | Select-Object -First 1 | ForEach-Object { Write-Info $_ }
  if ($LASTEXITCODE -ne 0) {
    Fail "ffmpeg -version failed"
  }

  Write-Info "Testing ffprobe binary: $FfprobeBinary"
  & $FfprobeBinary -version | Select-Object -First 1 | ForEach-Object { Write-Info $_ }
  if ($LASTEXITCODE -ne 0) {
    Fail "ffprobe -version failed"
  }

  $audioDir = Split-Path -Parent $AudioPath
  New-Item -ItemType Directory -Force -Path $audioDir | Out-Null
  & $FfmpegBinary -y -hide_banner -loglevel error -f lavfi -i "sine=frequency=1000:duration=1" -ac 1 -ar 16000 $AudioPath
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $AudioPath)) {
    Fail "ffmpeg could not generate smoke-test audio"
  }

  $duration = & $FfprobeBinary -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $AudioPath
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($duration)) {
    Fail "ffprobe could not read generated smoke-test audio"
  }
  Write-Ok "ffmpeg/ffprobe smoke test passed. Generated audio duration: $duration sec"
}

function Mask-Secret {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return ""
  }
  if ($Value.Length -lt 10) {
    return "***"
  }
  return "$($Value.Substring(0, 3))***$($Value.Substring($Value.Length - 3))"
}

function Get-ModelsUrl {
  param([string]$BaseUrl)
  $base = ($BaseUrl.TrimEnd("/"))
  if ($base.EndsWith("/v1")) {
    return "$base/models"
  }
  return "$base/v1/models"
}

function Test-ProviderKey {
  param(
    [string]$Name,
    [string]$BaseUrl,
    [string]$ApiKey
  )

  if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Info "$Name API key is not present; skipping validation."
    return $true
  }

  $url = Get-ModelsUrl $BaseUrl
  Write-Info "Validating $Name API key $(Mask-Secret $ApiKey) against $url"
  try {
    $headers = @{ Authorization = "Bearer $ApiKey" }
    $resp = Invoke-WebRequest -Uri $url -Headers $headers -Method GET -UseBasicParsing -TimeoutSec 30
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
      Write-Ok "$Name API key validation passed."
      return $true
    }
    Write-Warn "$Name API key validation returned HTTP $($resp.StatusCode)"
    return $false
  } catch {
    $statusCode = $null
    if ($_.Exception.Response) {
      try { $statusCode = [int]$_.Exception.Response.StatusCode } catch { $statusCode = $null }
    }
    if ($statusCode) {
      Write-Warn "$Name API key validation failed with HTTP $statusCode"
    } else {
      Write-Warn "$Name API key validation failed: $($_.Exception.Message)"
    }
    return $false
  }
}

function Test-PortOpen {
  param(
    [string]$HostValue,
    [int]$PortValue
  )
  try {
    $client = New-Object Net.Sockets.TcpClient
    $iar = $client.BeginConnect($HostValue, $PortValue, $null, $null)
    $connected = $iar.AsyncWaitHandle.WaitOne(500, $false)
    if ($connected) {
      $client.EndConnect($iar)
      $client.Close()
      return $true
    }
    $client.Close()
    return $false
  } catch {
    return $false
  }
}

function Get-FreePort {
  $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 0)
  $listener.Start()
  $portValue = $listener.LocalEndpoint.Port
  $listener.Stop()
  return [int]$portValue
}

function Wait-ForHealth {
  param(
    [string]$BaseUrl,
    [int]$TimeoutSec,
    [System.Diagnostics.Process]$Process
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if ($Process.HasExited) {
      Fail "uvicorn exited before health check passed. Exit code: $($Process.ExitCode)"
    }
    try {
      $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 5
      if ($health.status -eq "ok") {
        Write-Ok "API health check passed at $BaseUrl/health"
        return
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  Fail "API did not become healthy within $TimeoutSec seconds"
}

function Stop-ProcessSafe {
  param([System.Diagnostics.Process]$Process)
  if ($Process -and -not $Process.HasExited) {
    try {
      $Process.Kill()
      $Process.WaitForExit(5000) | Out-Null
    } catch {
      Write-Warn "Could not stop process $($Process.Id): $($_.Exception.Message)"
    }
  }
}

function Stop-ProcessTreeSafe {
  param([System.Diagnostics.Process]$Process)
  if (-not $Process) {
    return
  }

  $pidValue = [int]$Process.Id
  try {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$pidValue" -ErrorAction SilentlyContinue)
    foreach ($child in $children) {
      try {
        $childProc = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
        if ($childProc) {
          Stop-ProcessTreeSafe -Process $childProc
        }
      } catch {
        Write-Warn "Could not inspect child process $($child.ProcessId): $($_.Exception.Message)"
      }
    }
  } catch {
    Write-Warn "Could not enumerate child processes for $pidValue`: $($_.Exception.Message)"
  }

  Stop-ProcessSafe -Process $Process
}

function Run-PythonHere {
  param(
    [string]$PythonExe,
    [string]$ScriptText,
    [string[]]$Arguments = @()
  )
  $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("tootak_bootstrap_" + [guid]::NewGuid().ToString("N") + ".py")
  Set-Content -Path $tmp -Value $ScriptText -Encoding UTF8
  try {
    & $PythonExe $tmp @Arguments
    if ($LASTEXITCODE -ne 0) {
      Fail "Python helper failed with exit code $LASTEXITCODE"
    }
  } finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  }
}

try {
  Write-Stage "Locate project and validate Windows environment"
  $isWindowsRuntime = $env:OS -eq "Windows_NT"
  $isWindowsVariable = Get-Variable -Name IsWindows -ErrorAction SilentlyContinue
  if ($isWindowsVariable) {
    $isWindowsRuntime = [bool]$isWindowsVariable.Value
  }
  if (-not $isWindowsRuntime) {
    Fail "This script is for Windows PowerShell/PowerShell on Windows."
  }
  Write-BootstrapHelp
  $scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
  Set-Location $repoRoot
  if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $repoRoot
  } elseif (-not ($env:PYTHONPATH.Split(";") -contains $repoRoot)) {
    $env:PYTHONPATH = "$repoRoot;$env:PYTHONPATH"
  }
  Write-Ok "Repository root: $repoRoot"

  Write-Stage "Resolve Python 3.10+ and prepare virtual environment"
  $pythonExe = Resolve-PythonExecutable -PreferredPython $Python -RepoRoot $repoRoot
  $venvDir = Join-Path $repoRoot ".venv"
  $venvPython = Join-Path $venvDir "Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    Invoke-Native -Label "Creating virtual environment at .venv" -FilePath $pythonExe -Arguments @("-m", "venv", $venvDir)
  } else {
    Write-Ok "Virtual environment already exists: $venvDir"
  }
  if (-not (Test-Path $venvPython)) {
    Fail "Virtual environment Python was not found at $venvPython"
  }

  Write-Stage "Install and verify Python packages"
  if ($SkipPackageInstall) {
    Write-Warn "Skipping pip install because -SkipPackageInstall was provided. Import verification will still run."
  } else {
    Invoke-Native -Label "Upgrading pip/setuptools/wheel" -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    Invoke-Native -Label "Installing requirements.txt" -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt")
  }

  $importCheck = @'
import importlib
mods = ["fastapi", "uvicorn", "httpx", "multipart", "pydantic", "yaml", "dotenv", "pytest", "faster_whisper", "ctranslate2"]
missing = []
for name in mods:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")
if missing:
    raise SystemExit("Missing imports:\n" + "\n".join(missing))
print("Python import check passed:", ", ".join(mods))
'@
  Run-PythonHere -PythonExe $venvPython -ScriptText $importCheck

  Write-Stage "Create configuration files and runtime directories"
  $envFile = Join-Path $repoRoot ".env"
  $envExample = Join-Path $repoRoot ".env.example"
  $configFile = Join-Path $repoRoot "config\config.yml"
  $configExample = Join-Path $repoRoot "config\config.example.yml"

  if (-not (Test-Path $envFile)) {
    Copy-Item -Path $envExample -Destination $envFile
    $script:CreatedEnvFile = $true
    Write-Ok "Created .env from .env.example"
  } else {
    Write-Ok ".env already exists; existing values are preserved."
  }

  if (-not (Test-Path $configFile)) {
    Copy-Item -Path $configExample -Destination $configFile
    Write-Ok "Created config/config.yml from config/config.example.yml"
  } else {
    Write-Ok "config/config.yml already exists; existing values are preserved."
  }

  if ($script:CreatedEnvFile) {
    Set-EnvFileValue -FilePath $envFile -Key "LOCAL_MODEL_ID" -Value $LocalModelId
    Set-EnvFileValue -FilePath $envFile -Key "LOCAL_DEVICE" -Value "cpu"
    Set-EnvFileValue -FilePath $envFile -Key "LOCAL_COMPUTE_TYPE" -Value "int8"
    Write-Ok "Fresh .env tuned for first-run CPU reliability: APP_PORT=8030, LOCAL_MODEL_ID=$LocalModelId, LOCAL_DEVICE=cpu, LOCAL_COMPUTE_TYPE=int8"
  }

  Migrate-DefaultPort -EnvFile $envFile

  Import-DotEnv -FilePath $envFile
  [Environment]::SetEnvironmentVariable("APP_CONFIG_FILE", (Get-EnvValue "APP_CONFIG_FILE" "config/config.yml"), "Process")

  $runtimeDir = Get-EnvValue "STORAGE_RUNTIME_DIR" "runtime"
  $uploadDir = Get-EnvValue "STORAGE_UPLOAD_DIR" "runtime/uploads"
  $outputDir = Get-EnvValue "STORAGE_OUTPUT_DIR" "runtime/outputs"
  $modelDir = Get-EnvValue "STORAGE_MODEL_DIR" "runtime/models"
  foreach ($dir in @($runtimeDir, $uploadDir, $outputDir, $modelDir, "runtime/logs", "runtime/smoke")) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  Write-Ok "Runtime directories are ready."

  Write-Stage "Ensure ffmpeg and ffprobe are available"
  $ffmpegBinary = Get-EnvValue "PROCESSING_FFMPEG_BINARY" "ffmpeg"
  $ffprobeBinary = Get-EnvValue "PROCESSING_FFPROBE_BINARY" "ffprobe"
  if ((-not (Test-BinaryAvailable $ffmpegBinary)) -or (-not (Test-BinaryAvailable $ffprobeBinary))) {
    if ($SkipFFmpegInstall) {
      Fail "ffmpeg/ffprobe are missing and -SkipFFmpegInstall was provided."
    }
    Write-Warn "ffmpeg or ffprobe missing. Installation will be attempted."
    $installed = Install-FFmpegWithWinget
    if (-not $installed) {
      $installed = Install-FFmpegManually -RepoRoot $repoRoot -EnvFile $envFile
    }
    if (-not $installed) {
      Fail "ffmpeg installation failed."
    }
    Import-DotEnv -FilePath $envFile
  } else {
    Write-Ok "ffmpeg and ffprobe are already available."
  }

  $ffmpegBinary = Get-EnvValue "PROCESSING_FFMPEG_BINARY" "ffmpeg"
  $ffprobeBinary = Get-EnvValue "PROCESSING_FFPROBE_BINARY" "ffprobe"
  $smokeAudio = Join-Path $repoRoot "runtime\smoke\sample-tone.wav"
  Test-FFmpeg -FfmpegBinary $ffmpegBinary -FfprobeBinary $ffprobeBinary -AudioPath $smokeAudio

  Write-Stage "Validate application settings"
  $settingsCheck = @'
from api.app.config import get_settings
s = get_settings()
print("Settings loaded")
print("App:", s.app.name, s.app.version)
print("Host/Port:", s.app.host, s.app.port)
print("Default provider:", s.transcription.default_provider)
print("Local model:", s.local.model_id, s.local.device, s.local.compute_type)
print("Runtime dir:", s.storage.runtime_dir)
'@
  Run-PythonHere -PythonExe $venvPython -ScriptText $settingsCheck

  Write-Stage "Optionally preload local faster-whisper model"
  if ($SkipLocalModelDownload) {
    Write-Warn "Skipping local model preload because -SkipLocalModelDownload was provided."
  } else {
    $hfMode = Prepare-HuggingFaceAccess -EnvFile $envFile -ProvidedToken $HfToken
    if ($hfMode -eq "skip-model") {
      Write-Warn "Skipping local model preload by user choice."
    } else {
      $env:BOOTSTRAP_LOCAL_MODEL_ID = $LocalModelId
      Write-Info "Preparing local model '$LocalModelId'. First download may take several minutes depending on network speed."
      Write-StepDetail "Approx sizes: tiny ~75MB, small ~465MB, medium ~1.5GB, large-v3 ~3GB. Use -SkipLocalModelDownload to skip this stage."
      $modelCheck = @'
import os
import logging
import warnings
from api.app.config import get_settings
from faster_whisper import WhisperModel

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="huggingface_hub")

s = get_settings()
model_id = os.getenv("BOOTSTRAP_LOCAL_MODEL_ID") or s.local.model_id
print(f"Preparing faster-whisper model: {model_id}")
WhisperModel(
    model_id,
    device="cpu",
    compute_type="int8",
    download_root=s.storage.model_dir,
    cpu_threads=max(1, int(s.local.cpu_threads or 1)),
    num_workers=max(1, int(s.local.num_workers or 1)),
)
print("Local model is ready")
'@
      try {
        Run-PythonHere -PythonExe $venvPython -ScriptText $modelCheck
        $script:LocalModelReady = $true
        Write-Ok "Local model preload passed."
      } catch {
        if ($RequireLocalModel) {
          throw
        }
        Write-Warn "Local model preload failed, but setup will continue. Use -RequireLocalModel to make this fatal. Error: $($_.Exception.Message)"
        $script:LocalModelReady = $false
      }
    }
  }

  Write-Stage "Run project test suite"
  if ($SkipTests) {
    Write-Warn "Skipping pytest because -SkipTests was provided."
  } else {
    Invoke-Native -Label "Running pytest -q" -FilePath $venvPython -Arguments @("-m", "pytest", "-q")
    Write-Ok "pytest passed."
  }

  Write-Stage "Validate configured API keys"
  if ($SkipApiKeyValidation) {
    Write-Warn "Skipping API key validation because -SkipApiKeyValidation was provided."
  } else {
    $keyResults = @()
    $openaiProviderKey = Get-EnvValue "PROVIDER_OPENAI_API_KEY" ""
    $openaiProviderBase = Get-EnvValue "PROVIDER_OPENAI_BASE_URL" "https://api.openai.com"
    $groqKey = Get-EnvValue "PROVIDER_GROQ_API_KEY" ""
    $groqBase = Get-EnvValue "PROVIDER_GROQ_BASE_URL" "https://api.groq.com/openai"
    $workerOpenAIKey = Get-EnvValue "OPENAI_API_KEY" ""
    $workerOpenAIBase = Get-EnvValue "OPENAI_BASE_URL" "https://api.gapgpt.app/v1"

    $keyResults += Test-ProviderKey -Name "provider.openai" -BaseUrl $openaiProviderBase -ApiKey $openaiProviderKey
    $keyResults += Test-ProviderKey -Name "provider.groq" -BaseUrl $groqBase -ApiKey $groqKey
    if ($workerOpenAIKey -and ($workerOpenAIKey -ne $openaiProviderKey -or $workerOpenAIBase -ne $openaiProviderBase)) {
      $keyResults += Test-ProviderKey -Name "queue-worker.openai" -BaseUrl $workerOpenAIBase -ApiKey $workerOpenAIKey
    }

    if ($FailOnInvalidApiKey -and ($keyResults -contains $false)) {
      Fail "At least one configured API key failed validation."
    }
  }

  Write-Stage "Start temporary API server and run smoke tests"
  $configuredPort = if ($Port -gt 0) { $Port } else { [int](Get-EnvValue "APP_PORT" "8030") }
  if ($SkipSmokeTests) {
    Write-Warn "Skipping API smoke tests because -SkipSmokeTests was provided."
    $smokePort = $null
    $apiProcess = $null
  } else {
  $smokePort = Get-FreePort
  Write-Info "Smoke server will use temporary port $smokePort. Final service port remains $configuredPort."

  $env:APP_HOST = $HostName
  $env:APP_PORT = [string]$smokePort
  $apiOutLog = Join-Path $repoRoot "runtime\logs\bootstrap-api.stdout.log"
  $apiErrLog = Join-Path $repoRoot "runtime\logs\bootstrap-api.stderr.log"
  Remove-Item -LiteralPath $apiOutLog, $apiErrLog -Force -ErrorAction SilentlyContinue

  $apiProcess = Start-Process -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "api.app.main:app", "--host", $HostName, "--port", [string]$smokePort, "--log-level", "info") `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $apiOutLog `
    -RedirectStandardError $apiErrLog `
    -WindowStyle Hidden `
    -PassThru

  $baseUrl = "http://$HostName`:$smokePort"
  try {
    Wait-ForHealth -BaseUrl $baseUrl -TimeoutSec $StartupTimeoutSec -Process $apiProcess
    $doLocalSmoke = if ($script:LocalModelReady) { "1" } else { "0" }
    $smokeRunner = @'
import os
import sys
import time
import httpx

base_url = sys.argv[1].rstrip("/")
audio_path = sys.argv[2]
do_local = sys.argv[3] == "1"
timeout = float(sys.argv[4])

admin_headers = {}
if os.getenv("ADMIN_REQUIRE_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}:
    header_name = os.getenv("ADMIN_HEADER_NAME", "x-admin-token")
    token = os.getenv("ADMIN_TOKEN", "")
    if token:
        admin_headers[header_name] = token

def assert_status(resp, expected=200):
    if resp.status_code != expected:
        raise AssertionError(f"{resp.request.method} {resp.request.url} returned {resp.status_code}: {resp.text[:500]}")

with httpx.Client(timeout=httpx.Timeout(timeout), trust_env=False) as client:
    health = client.get(f"{base_url}/health")
    assert_status(health)
    h = health.json()
    assert h["status"] == "ok", h
    assert h["ffmpeg_available"] is True, h
    assert h["ffprobe_available"] is True, h

    providers = client.get(f"{base_url}/providers")
    assert_status(providers)
    assert "providers" in providers.json()

    openapi = client.get(f"{base_url}/openapi.json")
    assert_status(openapi)
    assert "/health" in openapi.text

    docs = client.get(f"{base_url}/docs")
    assert docs.status_code in (200, 404), docs.status_code

    effective = client.get(f"{base_url}/admin/system/config-effective", headers=admin_headers)
    assert_status(effective)
    cfg = effective.json()["config"]
    assert cfg["storage"]["runtime_dir"]

    presets = client.get(f"{base_url}/admin/models/presets", headers=admin_headers)
    assert_status(presets)
    assert presets.json()["total"] >= 1

    local_models = client.get(f"{base_url}/admin/models/local", headers=admin_headers)
    assert_status(local_models)

    url_payload = {"repo_id": "Systran/faster-whisper-tiny", "filename": "config.json", "revision": "main"}
    hf_url = client.post(f"{base_url}/admin/models/url/huggingface-file", json=url_payload, headers=admin_headers)
    assert_status(hf_url)
    assert "huggingface.co" in hf_url.json()["url"]

    try:
        remote = client.get(f"{base_url}/admin/models/remote/repos", params={"query": "faster-whisper", "limit": 1}, headers=admin_headers)
        if remote.status_code == 200:
            print("Remote model search smoke passed.")
        else:
            print(f"Remote model search skipped/warn: HTTP {remote.status_code}")
    except Exception as exc:
        print(f"Remote model search skipped/warn: {exc}")

    if do_local:
        with open(audio_path, "rb") as fh:
            files = {"file": ("sample-tone.wav", fh, "audio/wav")}
            data = {
                "provider": "local",
                "model": os.getenv("BOOTSTRAP_LOCAL_MODEL_ID", os.getenv("LOCAL_MODEL_ID", "tiny")),
                "language": "en",
                "response_format": "verbose_json",
                "word_timestamps": "false",
                "segment_timestamps": "false",
                "beam_size": "1",
                "best_of": "1",
                "vad_filter": "false",
            }
            resp = client.post(f"{base_url}/transcribe", data=data, files=files)
        assert_status(resp)
        body = resp.json()
        assert "text" in body
        assert body["usage"]["provider"] == "local"
        print("Local transcription smoke passed.")
    else:
        print("Local transcription smoke skipped because local model is not ready.")

print("API smoke tests passed.")
'@
    Run-PythonHere -PythonExe $venvPython -ScriptText $smokeRunner -Arguments @($baseUrl, $smokeAudio, $doLocalSmoke, [string]$SmokeTimeoutSec)
    Write-Ok "API smoke tests passed."
  } finally {
    Stop-ProcessTreeSafe -Process $apiProcess
  }
  }

  Write-Stage "Finish setup"
  Write-Ok "Windows setup completed successfully."
  Write-Info "Web UI: http://$HostName`:$configuredPort/"
  Write-Info "Swagger UI: http://$HostName`:$configuredPort/docs"
  Write-Info "Logs: runtime/logs/"

  if ($SetupOnly -or $NoStart) {
    Write-Ok "Service start skipped."
    exit 0
  }

  Write-Stage "Start API service in foreground"
  if (Test-PortOpen -HostValue $HostName -PortValue $configuredPort) {
    Fail "Configured port $configuredPort is already in use. Stop the existing process or rerun with -Port <free-port>."
  }
  $env:APP_HOST = $HostName
  $env:APP_PORT = [string]$configuredPort
  Write-Info "Starting uvicorn. Press Ctrl+C to stop."
  & $venvPython -m uvicorn api.app.main:app --host $HostName --port $configuredPort --reload
  if ($LASTEXITCODE -ne 0) {
    Fail "uvicorn exited with code $LASTEXITCODE"
  }
} catch {
  Write-Log "FAILED" $_.Exception.Message Red
  Write-Info "If uvicorn failed during smoke tests, check runtime/logs/bootstrap-api.stderr.log"
  exit 1
}
