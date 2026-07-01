# REELS AI — Windows guide

REELS AI is a local Streamlit desktop web application for producing 1080×1920 reels from a script, ordered images, voiceover, music, and one-word synchronized captions.

## First-time setup

1. Install **64-bit Python 3.11** from [python.org](https://www.python.org/downloads/release/python-3119/). During installation, select **Add Python to PATH** and install the Python launcher.
2. Double-click `setup_windows.bat`. It creates `.venv`, installs the pinned packages, downloads the project-local FFmpeg binary through `imageio-ffmpeg`, and verifies imports.
3. Setup can take several minutes because `faster-whisper` includes speech-recognition dependencies.

## Start, stop, and restart

Double-click `start_reels_ai.bat`. Keep its terminal window open while using the app. It opens at <http://localhost:8501>. To stop it, close that terminal with Ctrl+C or run `stop_reels_ai.bat`. Restart by double-clicking the start file again.

## Main workflow

Paste the script, upload scene images in order, choose generated or uploaded voiceover, and select **Generate timestamps**. Inspect or correct the alignment table, choose image anchors and styling, then select **Generate Reel**. The completed video appears in the same preview and can be downloaded.

Edge TTS voice generation requires internet access. The first timestamp generation downloads the faster-whisper `base.en` model into `models/`; the app shows download progress and later uses are fully local. Uploaded voiceovers, rendering, previews, project storage, and local music work offline after setup/model download.

## Files and folders

- `output/` — rendered MP4 files, `word_alignment.json`, and `reels_ai.log`
- `projects/<project-name>/` — saved drafts and their copied assets
- `assets/fonts/` — optional user-provided fonts
- `assets/music/<category>/` — local background tracks
- `temp/` — sanitized working copies of uploads

## Fonts

The app checks `assets/fonts/` first and then Windows Fonts. Add legally licensed `.ttf` files using the documented filenames, such as `Poppins-ExtraBold.ttf`, `Montserrat-ExtraBold.ttf`, `Anton-Regular.ttf`, or `BebasNeue-Regular.ttf`. Missing fonts generate a visible warning and use an Arial/built-in fallback.

## Music

Copy MP3, WAV, M4A, OGG, or FLAC files into the matching folder under `assets/music/` (`calm-islamic`, `mystery`, `cinematic`, `facts`, `emotional`, or `ambient`). REELS AI never downloads copyrighted tracks. Empty folders are safe and render without music.

## FFmpeg troubleshooting

FFmpeg is resolved from `imageio-ffmpeg`; no global installation is required. If setup reports an FFmpeg error, verify internet access during setup, delete `.venv`, rerun `setup_windows.bat`, and check that antivirus software did not quarantine the executable. Technical errors are recorded in `output/reels_ai.log`.

## Performance and accuracy

1080×1920 rendering is CPU-intensive, but REELS AI uses a native FFmpeg renderer rather than processing every frame in Python. **Fast** is the recommended default; **Balanced** trades some speed for smoother photo motion, and **Maximum quality** is slowest. All profiles export captions and video at 30 fps. The `base.en` Whisper model balances speed and accuracy; unusual transliterations may need correction in the alignment table. Static preview shows representative caption styling but not the selected animation. Crossfade/fade are implemented; slide and cinematic-reveal use the same restrained fade treatment. Image timing modes other than word anchoring distribute each image once across actual audio duration.
