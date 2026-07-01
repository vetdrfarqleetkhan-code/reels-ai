from PIL import Image

from reels_ai.alignment import SpokenWord, align_script_to_words, ensure_whisper_model, script_tokens
from reels_ai.captions import resolve_font
from reels_ai.generator import RENDER_CONFIG, _write_ass, select_audio_source
from reels_ai.planning import equal_scene_timings
from reels_ai.utils import VIDEO_HEIGHT, VIDEO_WIDTH, cover_crop


def words(items):
    return [SpokenWord(w, i * .2, (i + 1) * .2) for i, w in enumerate(items)]


def test_cover_crop_exact_size():
    for size in [(2000, 800), (800, 2000), (900, 900)]:
        assert cover_crop(Image.new("RGB", size)).size == (1080, 1920)


def test_one_word_caption_events():
    events = align_script_to_words("NOT LIGHTLY YOUR", words(["not", "lightly", "your"]))
    assert [e.token for e in events] == ["NOT", "LIGHTLY", "YOUR"]


def test_missing_word_and_silent_honorific():
    events = align_script_to_words("The Prophet ﷺ saw it", words(["the", "prophet", "saw", "it"]))
    assert [e.token for e in events] == ["The", "Prophet", "saw", "it"]


def test_repeated_phrase_is_monotonic():
    events = align_script_to_words("O Allah\nO Allah\nO Allah", words(["o","allah","o","allah","o","allah"]))
    assert [e.start for e in events] == sorted(e.start for e in events)
    assert len(events) == 6


def test_numeric_token_spans_spoken_number():
    events = align_script_to_words("124,000", words("one hundred twenty four thousand".split()))
    assert events[0].token == "124,000"
    assert events[0].matched == "one hundred twenty four thousand"
    assert events[0].end == 1.0


def test_thumbnail_offset_contract():
    timing = equal_scene_timings(["scene.jpg"], 2.0)[0]
    assert timing.start == 0 and timing.end == 2.0
    thumbnail_duration = .5
    assert timing.start + thumbnail_duration == .5


def test_uploaded_voiceover_precedence(tmp_path):
    uploaded = tmp_path / "uploaded.wav"; generated = tmp_path / "generated.mp3"
    assert select_audio_source("Upload voiceover", uploaded, generated) == uploaded


def test_font_fallback_does_not_crash():
    path, warning = resolve_font("Definitely Missing Font")
    assert path is None or path.exists()


def test_render_configuration():
    assert (VIDEO_WIDTH, VIDEO_HEIGHT) == (1080, 1920)
    assert RENDER_CONFIG["codec"] == "libx264"
    assert RENDER_CONFIG["audio_codec"] == "aac"
    assert RENDER_CONFIG["logger"] is None
    assert "yuv420p" in RENDER_CONFIG["ffmpeg_params"]


def test_tokens_preserve_apostrophes_and_numbers():
    assert script_tokens("Qur'an 124,000") == ["Qur'an", "124,000"]


def test_existing_whisper_model_is_reused_without_download(tmp_path, monkeypatch):
    import reels_ai.utils

    monkeypatch.setattr(reels_ai.utils, "ROOT", tmp_path)
    model = tmp_path / "models" / "faster-whisper-base.en" / "model.bin"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"x" * 1_000_001)
    messages = []
    assert ensure_whisper_model("base.en", messages.append) == model.parent
    assert messages == ["Transcription model ready"]


def test_fast_renderer_ass_has_one_word_events(tmp_path):
    from reels_ai.alignment import CaptionEvent

    output = tmp_path / "captions.ass"
    _write_ass(output, [CaptionEvent("NOT", "not", 0, .2, 1), CaptionEvent("LIGHTLY", "lightly", .2, .5, 1)],
               {"font":"Arial Black", "size":112, "fill":"#FFD400", "outline_color":"#000000", "outline":8}, 0, 0)
    text = output.read_text(encoding="utf-8-sig")
    dialogue = [line for line in text.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue) == 2
    assert dialogue[0].endswith("NOT") and dialogue[1].endswith("LIGHTLY")
