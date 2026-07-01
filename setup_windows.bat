@echo off
setlocal
cd /d "%~dp0"
echo [REELS AI] Checking Python...
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher was not found. Install Python 3.11 from python.org and enable "Add Python to PATH".
  pause
  exit /b 1
)
py -3.11 --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 was not found. Install Python 3.11, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
if errorlevel 1 goto :fail
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
set PYTHONPATH=%CD%\src
python -c "import streamlit,PIL,imageio_ffmpeg,edge_tts,faster_whisper; from reels_ai.utils import ffmpeg_executable; print('FFmpeg:', ffmpeg_executable())"
if errorlevel 1 goto :fail
echo.
echo SUCCESS: REELS AI is ready. Double-click start_reels_ai.bat.
pause
exit /b 0
:fail
echo.
echo ERROR: Setup failed. Review the message above and output\reels_ai.log if present.
pause
exit /b 1
