@echo off
:: VisionForge — Start Services
:: Double-click this file or use the Desktop / Start Menu shortcut.
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%start-visionforge.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [VisionForge] Startup failed. See the output above for details.
    pause
)
