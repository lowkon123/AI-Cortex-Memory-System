@echo off
setlocal
cd /d "d:\Projects\Antigravity\AI_mem_system"

:: Step 1: Force kill any existing processes on 8002 and 8000
echo Cleaning existing processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8002') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1

:: Step 2: Start DB (Force remove existing container first to fix name conflict)
echo Starting Postgres...
docker rm -f cortex-postgres >nul 2>&1
docker-compose up -d postgres


:: Step 3: Wait for DB initialization (extended to 10s)
echo Waiting for Database (10 seconds)...
timeout /t 10 /nobreak >nul

:: Step 4: Start local API
echo Starting API...
start "Cortex-API" /b python -m uvicorn api.main:app --host 127.0.0.1 --port 8002

:: Step 5: Start Dashboard
echo Starting Dashboard...
start "Cortex-Dashboard" /b python dashboard.py

echo Done. Cortex is running.
exit


