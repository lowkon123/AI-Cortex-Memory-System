@echo off
title Cortex Service Killer
echo 正在清理佔用 8000 (Dashboard) 和 8002 (API) 埠號的進程...

:: 尋找並結束佔用特定埠號的進程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8002 ^| findstr LISTENING') do taskkill /f /pid %%a

echo.
echo 清理完成！現在你可以再次執行 launch_services.bat 了。
pause
