@echo off
echo Stopping the REELS AI server on port 8501...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
echo Done. You may close this window.
pause

