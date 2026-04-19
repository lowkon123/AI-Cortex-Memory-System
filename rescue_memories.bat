@echo off
setlocal
cd /d "d:\Projects\Antigravity\AI_mem_system"

echo Step 1: Stopping all services...
docker-compose down

echo.
echo Step 2: Rescuing memories from 'antigravity_postgres_data'...
:: 使用臨時容器將 Docker 內部的資料複製出來
docker run --rm -v "antigravity_postgres_data:/from" -v "%cd%\data\postgres:/to" alpine sh -c "cp -av /from/. /to/"

echo.
echo Step 3: Rescuing memories from 'ai_mem_system_postgres_data' (if exists)...
docker run --rm -v "ai_mem_system_postgres_data:/from" -v "%cd%\data\postgres:/to" alpine sh -c "cp -av /from/. /to/"

echo.
echo Step 4: Restarting Cortex with PERMANENT storage...
docker-compose up -d postgres

echo.
echo Success! Your memories are now stored permanently in:
echo d:\Projects\Antigravity\AI_mem_system\data\postgres
pause
