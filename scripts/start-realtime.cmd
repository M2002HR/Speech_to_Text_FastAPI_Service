@echo off
setlocal
cd /d "%~dp0.."

where powershell >nul 2>nul
if errorlevel 1 (
  echo PowerShell was not found.
  exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0start-realtime.ps1" %*
