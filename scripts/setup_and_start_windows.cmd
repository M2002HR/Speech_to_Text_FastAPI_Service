@echo off
setlocal
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0setup_and_start_windows.ps1" -NoStart %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" goto done
powershell -ExecutionPolicy Bypass -File "%~dp0start_windows.ps1"
set EXITCODE=%ERRORLEVEL%
:done
echo.
echo Script finished with exit code %EXITCODE%.
pause
exit /b %EXITCODE%
