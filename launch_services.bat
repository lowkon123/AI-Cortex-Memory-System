@echo off
setlocal
title Cortex Memory Launcher
cd /d "d:\Projects\Antigravity\AI_mem_system"

echo ==========================================
echo    Cortex Memory Engine - Service Starter
echo ==========================================

:: 1. 啟動 API (Port 8002)
echo [1/2] Launching AI Memory API (8002)...
start "Cortex-API-8002" cmd /k "python -m uvicorn api.main:app --host 127.0.0.1 --port 8002"

:: 等待 2 秒確保 API 先起來
timeout /t 2 >nul

:: 2. 啟動 Dashboard (Port 8000)
echo [2/2] Launching 3D Dashboard (8000)...
start "Cortex-Dashboard-8000" cmd /k "python dashboard.py"

echo.
echo ------------------------------------------
echo 服務已在獨立視窗啟動：
echo API: http://127.0.0.1:8002
echo Dashboard: http://127.0.0.1:8000
echo ------------------------------------------
pause
