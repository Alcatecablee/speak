@echo off
title Speak V2 - Local Engine
echo ============================================================================
echo   SPEAK V2 - LOCAL CALL CAPTURE ^& INTELLIGENCE ENGINE
echo ============================================================================
echo.
echo Starting Speak Localhost Engine on http://127.0.0.1:8765 ...
echo (Keep this window open while using Speak in your browser)
echo.
python -m local_engine.server
pause
