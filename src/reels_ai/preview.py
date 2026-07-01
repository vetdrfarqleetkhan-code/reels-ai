from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from .captions import draw_caption
from .utils import VIDEO_HEIGHT, VIDEO_WIDTH, cover_crop


def static_preview(image_bytes: bytes | None, caption: str, settings: dict, platform: str, guides: bool) -> bytes:
    if image_bytes:
        image = cover_crop(Image.open(BytesIO(image_bytes)))
    else:
        image = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), "#151821")
        draw = ImageDraw.Draw(image)
        draw.text((VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2), "UPLOAD A SCENE", anchor="mm", fill="#8A91A3")
    if caption: image = draw_caption(image, caption, settings)
    if guides:
        draw = ImageDraw.Draw(image, "RGBA")
        margins = {"Instagram Reel": (90, 220, 180, 320), "YouTube Shorts": (80, 180, 200, 350), "TikTok": (80, 220, 210, 380)}[platform]
        draw.rectangle((margins[0], margins[1], VIDEO_WIDTH-margins[2], VIDEO_HEIGHT-margins[3]), outline=(255,255,255,150), width=4)
    output = BytesIO(); image.save(output, format="JPEG", quality=88); return output.getvalue()

