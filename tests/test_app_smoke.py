from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_has_stable_widget_keys_and_entrypoint():
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "set_page_config" in text
    assert "scene_uploader_{i}" in text
    assert "Generate Reel" in text
    assert 'disabled=not audio_ready' in text
    assert "Add or upload a script before generating timestamps." in text


def test_uploaded_voiceover_activates_timestamp_button(tmp_path):
    voiceover = tmp_path / "voiceover.wav"
    voiceover.write_bytes(b"uploaded audio placeholder")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20)
    app.run()
    app.session_state["voice_source"] = "Upload voiceover"
    app.session_state["audio_path"] = str(voiceover)
    app.run()
    timestamp_button = next(button for button in app.button if button.label == "Generate timestamps")
    assert timestamp_button.disabled is False
    assert not app.exception
