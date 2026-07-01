from __future__ import annotations

import hashlib
import logging
import re
import shutil
import os
import subprocess
from pathlib import Path

from PIL import Image

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output"
PROJECTS_DIR = ROOT / "projects"
TEMP_DIR = ROOT / "temp"
ASSETS_DIR = ROOT / "assets"


def ensure_directories() -> None:
    for path in (OUTPUT_DIR, PROJECTS_DIR, TEMP_DIR, ASSETS_DIR / "fonts"):
        path.mkdir(parents=True, exist_ok=True)


def configure_logging() -> logging.Logger:
    ensure_directories()
    logging.basicConfig(
        filename=OUTPUT_DIR / "reels_ai.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger("reels_ai")


def safe_name(value: str, default: str = "reel") -> str:
    value = Path(value).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip(" .")
    return cleaned[:100] or default


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cover_crop(image: Image.Image, size: tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)) -> Image.Image:
    """Resize with CSS cover semantics, then center crop."""
    image = image.convert("RGB")
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (max(target_w, round(image.width * scale)), max(target_h, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def ffmpeg_executable() -> str:
    import imageio_ffmpeg

    # Cloud Linux images install FFmpeg through the OS so filters such as
    # libass are available. Windows keeps using imageio-ffmpeg's bundled binary.
    system_ffmpeg = shutil.which("ffmpeg")
    if os.name != "nt" and system_ffmpeg:
        return str(Path(system_ffmpeg).resolve())
    path = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    if not path.exists():
        raise RuntimeError("The project-local FFmpeg executable could not be resolved.")
    return str(path)


def media_duration(path: Path) -> float:
    """Read media duration with FFmpeg, avoiding a second video framework."""
    result = subprocess.run(
        [ffmpeg_executable(), "-hide_banner", "-i", str(Path(path).resolve())],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise ValueError(f"Could not read the duration of {Path(path).name}.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
