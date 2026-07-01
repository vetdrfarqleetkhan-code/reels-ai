"""Create a tiny but real 1080x1920 MP4 for release verification."""
import math
import struct
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reels_ai.alignment import CaptionEvent
from reels_ai.generator import render_reel_fast
from reels_ai.planning import equal_scene_timings


def main() -> None:
    work = ROOT / "temp" / "smoke"
    work.mkdir(parents=True, exist_ok=True)
    scene = work / "scene.png"
    image = Image.new("RGB", (1080, 1920), "#172030")
    ImageDraw.Draw(image).ellipse((260, 680, 820, 1240), fill="#FFD400")
    image.save(scene)
    audio = work / "voice.wav"
    rate, duration = 22050, .65
    with wave.open(str(audio), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        for i in range(int(rate * duration)):
            sample = int(4000 * math.sin(2 * math.pi * 220 * i / rate))
            wav.writeframesraw(struct.pack("<h", sample))
    output = ROOT / "output" / "smoke_render.mp4"
    render_reel_fast([scene], equal_scene_timings([scene.name], duration), audio,
                [CaptionEvent("TEST", "test", .05, .55, 1.0)], output,
                {"font":"Arial Black","size":112,"fill":"#FFD400","outline_color":"#000000","outline":8,"position":"Lower middle","shadow":True,"uppercase":True},
                motion="None", transition="Cut")
    print(output, output.stat().st_size)


if __name__ == "__main__":
    main()
