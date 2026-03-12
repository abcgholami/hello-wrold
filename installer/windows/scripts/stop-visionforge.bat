@echo off
:: VisionForge — Stop Services
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%stop-visionforge.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [VisionForge] Stop command failed. See the output above.
    pause
)
