from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .alignment import CaptionEvent
from .utils import ASSETS_DIR, VIDEO_HEIGHT, VIDEO_WIDTH

FONT_CANDIDATES = {
    "Poppins": ["Poppins-ExtraBold.ttf", "Poppins-Bold.ttf"],
    "Montserrat": ["Montserrat-ExtraBold.ttf", "Montserrat-Bold.ttf"],
    "Anton": ["Anton-Regular.ttf"], "Bebas Neue": ["BebasNeue-Regular.ttf"],
    "Impact": ["impact.ttf"], "Arial Black": ["ariblk.ttf"], "Arial": ["arialbd.ttf", "arial.ttf"],
}


def resolve_font(name: str) -> tuple[Path | None, str | None]:
    font_dir = ASSETS_DIR / "fonts"
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for filename in FONT_CANDIDATES.get(name, []) + FONT_CANDIDATES["Arial"]:
        for folder in (font_dir, windows_fonts):
            candidate = folder / filename
            if candidate.exists():
                warning = None if filename in FONT_CANDIDATES.get(name, []) else f"{name} is unavailable; using Arial fallback."
                return candidate, warning
    return None, f"{name} is unavailable; using Pillow's built-in fallback."


def get_font(name: str, size: int) -> tuple[ImageFont.ImageFont, str | None]:
    path, warning = resolve_font(name)
    return (ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size=max(10, size))), warning


def caption_y(position: str) -> int:
    return {"Center": 960, "Lower middle": 1280, "Bottom safe": 1535}.get(position, 1280)


def draw_caption(image: Image.Image, text: str, settings: dict, scale: float = 1.0) -> Image.Image:
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    size = max(12, int(settings.get("size", 112) * scale))
    font, _ = get_font(settings.get("font", "Arial Black"), size)
    shown = text.upper() if settings.get("uppercase", True) else text
    box = draw.textbbox((0, 0), shown, font=font, stroke_width=int(settings.get("outline", 8) * scale))
    width, height = box[2] - box[0], box[3] - box[1]
    x, y = VIDEO_WIDTH / 2, caption_y(settings.get("position", "Lower middle"))
    if settings.get("shadow", True):
        draw.text((x + 8 * scale, y - height / 2 + 10 * scale), shown, anchor="ma", font=font, fill="#00000088", stroke_width=0)
    draw.text((x, y - height / 2), shown, anchor="ma", font=font,
              fill=settings.get("fill", "#FFD400"), stroke_width=int(settings.get("outline", 8) * scale),
              stroke_fill=settings.get("outline_color", "#000000"))
    return canvas


def event_at(events: list[CaptionEvent], t: float, offset: float = 0.0) -> CaptionEvent | None:
    adjusted = t - offset
    return next((event for event in events if event.start <= adjusted < event.end), None)

