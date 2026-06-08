@echo off
setlocal
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0start_windows.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
echo Script finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
