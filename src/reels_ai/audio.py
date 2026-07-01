from __future__ import annotations

import asyncio
import re
from pathlib import Path

import edge_tts

from .utils import safe_name

VOICE_PRESETS = {
    "Soft Islamic Mystic Narrator": "en-US-ChristopherNeural",
    "Warm Male Narrator": "en-GB-RyanNeural",
    "Calm Female Narrator": "en-US-JennyNeural",
}
SPEEDS = {"Slow": "-20%", "Slightly slow": "-10%", "Normal": "+0%", "Fast": "+15%"}

PRONUNCIATIONS = {
    "Qur'an": "Qur aan", "Hajj": "Haj", "Kaaba": "Kaa bah", "Hajr al-Aswad": "Hajar al Aswad",
    "Baitul Ma'mur": "Baytul Maamoor", "Ibrahim": "Ibraheem", "Jannah": "Jann-ah",
    "Jahannam": "Jahannam", "Akhirah": "Aa-khirah", "Qiyamah": "Qiyaamah", "Tawaf": "Tawaaf",
    "Isra wal Miraj": "Israa wal Mi'raaj", "Al-Ma'idah": "Al Maa-idah", "Muhammad": "Muhammad",
}


def prepare_tts_text(text: str, honorifics: str = "Keep visually only") -> str:
    result = text
    for original, spoken in sorted(PRONUNCIATIONS.items(), key=lambda x: -len(x[0])):
        result = re.sub(re.escape(original), spoken, result, flags=re.IGNORECASE)
    replacements = {"ﷺ": "peace be upon him", "(AS)": "peace be upon him", "(RA)": "may Allah be pleased with them"}
    for mark, spoken in replacements.items():
        if honorifics == "Speak full honorific":
            result = result.replace(mark, spoken)
        else:
            result = result.replace(mark, "")
    return re.sub(r"[ \t]+", " ", result).strip()


async def _save_tts(text: str, voice: str, rate: str, output: Path) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(output))


def generate_voiceover(text: str, output: Path, preset: str, speed: str, honorifics: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    voice = VOICE_PRESETS.get(preset, VOICE_PRESETS["Soft Islamic Mystic Narrator"])
    asyncio.run(_save_tts(prepare_tts_text(text, honorifics), voice, SPEEDS.get(speed, "-10%"), output))
    return output


def save_uploaded_audio(data: bytes, filename: str, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name(filename, "voiceover.mp3")
    path.write_bytes(data)
    return path

