@echo off
cd /d "%~dp0"
title Speak V2 - Local Engine
echo ============================================================================
echo   SPEAK V2 - LOCAL CALL CAPTURE ^& INTELLIGENCE ENGINE
echo ============================================================================
echo.
echo Working Directory: %CD%
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found on your system PATH.
    echo Please install Python 3.10+ and ensure 'Add Python to PATH' is checked.
    echo.
    pause
    exit /b 1
)

echo Starting Speak Localhost Engine on http://127.0.0.1:8765 ...
echo (Keep this console window open while running Speak in your browser)
echo.
python -m local_engine.server

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Speak Local Engine exited with error code %ERRORLEVEL%.
    pause
)
