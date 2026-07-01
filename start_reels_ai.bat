@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo REELS AI is not set up yet. Run setup_windows.bat first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
set PYTHONPATH=%CD%\src
echo Starting REELS AI at http://localhost:8501
python -m streamlit run app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
if errorlevel 1 (
  echo REELS AI stopped with an error. See output\reels_ai.log.
  pause
)

