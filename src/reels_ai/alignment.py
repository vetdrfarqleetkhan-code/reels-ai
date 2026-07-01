from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from num2words import num2words

SILENT_TOKENS = {"ﷺ", "(AS)", "(RA)"}
TOKEN_RE = re.compile(r"ﷺ|\((?:AS|RA)\)|\d[\d,]*(?:\.\d+)?|[^\W\d_]+(?:[’'\-][^\W\d_]+)*", re.UNICODE | re.IGNORECASE)
ALIASES = {
    "hajr": {"hajar"}, "aswad": {"alaswad"}, "kaaba": {"kaba", "kabah"}, "baitul": {"baytul"},
    "mamur": {"maamur", "mamoor"}, "ibrahim": {"ibraheem"}, "jannah": {"janna"},
    "quran": {"koran"}, "isra": {"israa"}, "miraj": {"miraaj"}, "tawaf": {"tawaaf"},
    "maidah": {"maida"}, "umar": {"omar"}, "ibn": {"bin"}, "alkhattab": {"khattab"},
}


@dataclass
class SpokenWord:
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class CaptionEvent:
    token: str
    matched: str
    start: float
    end: float
    confidence: float
    fallback: str = ""


def script_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def normalize(value: str) -> str:
    value = value.casefold().replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", "", value)


def variants(token: str) -> set[str]:
    base = normalize(token)
    values = {base}
    values.update(ALIASES.get(base, set()))
    if re.fullmatch(r"\d[\d,]*", token):
        try:
            values.add(normalize(num2words(int(token.replace(",", "")))))
        except (ValueError, OverflowError):
            pass
    return values


def _score(token: str, spoken_phrase: str) -> float:
    target = normalize(spoken_phrase)
    return max((SequenceMatcher(None, variant, target).ratio() for variant in variants(token)), default=0.0)


def align_script_to_words(script: str, spoken: list[SpokenWord]) -> list[CaptionEvent]:
    """Monotonic dynamic-programming alignment; numeric tokens may consume multiple words."""
    tokens = [t for t in script_tokens(script) if t.upper() not in SILENT_TOKENS]
    n, m = len(tokens), len(spoken)
    neg = -10**9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] <= neg / 2:
                continue
            if j < m and dp[i][j] - 0.35 > dp[i][j + 1]:
                dp[i][j + 1] = dp[i][j] - 0.35; back[i][j + 1] = (i, j, "skip-spoken")
            if i < n and dp[i][j] - 0.75 > dp[i + 1][j]:
                dp[i + 1][j] = dp[i][j] - 0.75; back[i + 1][j] = (i, j, "missing")
            if i < n:
                max_span = min(7 if re.fullmatch(r"\d[\d,]*", tokens[i]) else 3, m - j)
                for span in range(1, max_span + 1):
                    phrase = " ".join(w.word for w in spoken[j:j + span])
                    score = _score(tokens[i], phrase) - 0.04 * (span - 1)
                    if score > 0.42 and dp[i][j] + score > dp[i + 1][j + span]:
                        dp[i + 1][j + span] = dp[i][j] + score
                        back[i + 1][j + span] = (i, j, f"match:{span}:{score}")
    end_j = max(range(m + 1), key=lambda j: dp[n][j])
    matched: dict[int, tuple[int, int, float]] = {}
    i, j = n, end_j
    while i or j:
        b = back[i][j]
        if b is None: break
        pi, pj, action = b
        if action.startswith("match:"):
            _, span, score = action.split(":")
            matched[pi] = (pj, pj + int(span), float(score))
        i, j = pi, pj
    events: list[CaptionEvent] = []
    for index, token in enumerate(tokens):
        if index in matched:
            a, b, score = matched[index]
            events.append(CaptionEvent(token, " ".join(w.word for w in spoken[a:b]), spoken[a].start, spoken[b-1].end, score, "" if score >= .72 else "fuzzy"))
        else:
            prev = events[-1].end if events else (spoken[0].start if spoken else 0.0)
            next_start = next((spoken[a].start for k, (a, _, _) in matched.items() if k > index), prev + .25)
            start = min(prev, next_start)
            end = max(start + .06, next_start)
            events.append(CaptionEvent(token, "", start, end, 0.0, "interpolated"))
    for k in range(len(events) - 1):
        events[k].end = max(events[k].start + .01, min(events[k].end, events[k + 1].start))
    return events


def _model_repo(model_size: str) -> str:
    return f"Systran/faster-whisper-{model_size}"


def ensure_whisper_model(
    model_size: str = "base.en",
    progress: Callable[[str], None] | None = None,
    timeout_seconds: int = 900,
) -> Path:
    """Download a Whisper model once using plain HTTP, with feedback and a timeout.

    Hugging Face's optional Xet transport can stall indefinitely on some Windows
    installations. A separate process lets us disable it reliably and terminate a
    failed download without freezing Streamlit forever.
    """
    from .utils import ROOT

    progress = progress or (lambda _message: None)
    model_dir = ROOT / "models" / f"faster-whisper-{model_size}"
    model_bin = model_dir / "model.bin"
    if model_bin.exists() and model_bin.stat().st_size > 1_000_000:
        progress("Transcription model ready")
        return model_dir

    model_dir.mkdir(parents=True, exist_ok=True)
    progress("Downloading the transcription model (first use only)…")
    code = (
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download(repo_id={_model_repo(model_size)!r}, "
        f"local_dir={str(model_dir)!r})"
    )
    env = os.environ.copy()
    env["HF_HUB_DISABLE_XET"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=flags,
    )
    started = time.monotonic()
    while process.poll() is None:
        elapsed = int(time.monotonic() - started)
        if elapsed >= timeout_seconds:
            process.kill()
            process.wait()
            raise TimeoutError(
                "The transcription model download timed out. Check your internet "
                "connection, then click Generate timestamps again."
            )
        progress(f"Downloading transcription model… {elapsed}s elapsed")
        time.sleep(1)
    if process.returncode != 0 or not model_bin.exists() or model_bin.stat().st_size <= 1_000_000:
        raise RuntimeError(
            "The transcription model could not be downloaded. Check internet access "
            "and antivirus/firewall settings, then try again."
        )
    progress("Transcription model downloaded")
    return model_dir


def transcribe_audio(
    path: Path,
    model_size: str = "base.en",
    progress: Callable[[str], None] | None = None,
) -> list[SpokenWord]:
    from faster_whisper import WhisperModel

    progress = progress or (lambda _message: None)
    model_path = ensure_whisper_model(model_size, progress)
    progress("Loading transcription model locally…")
    model = WhisperModel(str(model_path), device="cpu", compute_type="int8", cpu_threads=max(1, min(8, os.cpu_count() or 4)))
    progress("Transcribing voiceover locally…")
    segments, _ = model.transcribe(
        str(path), word_timestamps=True, vad_filter=True, beam_size=1,
        condition_on_previous_text=True,
    )
    return [SpokenWord(w.word.strip(), w.start, w.end, w.probability) for s in segments for w in (s.words or []) if w.word.strip()]


def save_alignment(events: list[CaptionEvent], path: Path, script_hash: str = "", audio_hash: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"script_hash": script_hash, "audio_hash": audio_hash, "events": [asdict(e) for e in events]}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_alignment(path: Path) -> list[CaptionEvent]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [CaptionEvent(**event) for event in data["events"]]
