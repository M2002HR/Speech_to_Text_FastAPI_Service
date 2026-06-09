@echo off
REM ===========================================================================
REM Tootak - single Windows CMD entrypoint.
REM
REM Running this once installs everything and starts the full service
REM (transcription API + /live + /realtime). It simply forwards every argument
REM to the PowerShell launcher start.ps1, which does the real work.
REM
REM Examples:
REM   scripts\start.cmd
REM   scripts\start.cmd -Local -Port 9000
REM   scripts\start.cmd -NoStart -SkipTests
REM   scripts\start.cmd -EnvVars "DEEPGRAM_API_KEY=xxx","LIVE_LANGUAGE=en"
REM ===========================================================================
setlocal
cd /d "%~dp0.."

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell was not found on this system.
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1" %*
set EXITCODE=%ERRORLEVEL%

echo.
echo Script finished with exit code %EXITCODE%.
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
