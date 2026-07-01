from pathlib import Path


def test_app_has_stable_widget_keys_and_entrypoint():
    text = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "set_page_config" in text
    assert "scene_uploader_{i}" in text
    assert "Generate Reel" in text
