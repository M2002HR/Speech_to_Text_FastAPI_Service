from pathlib import Path


def test_live_panel_has_clear_microphone_errors_and_gpt_oss_default():
    live_html = Path(__file__).resolve().parents[1] / "api" / "app" / "ui" / "live.html"
    text = live_html.read_text(encoding="utf-8")
    assert "NotFoundError" in text
    assert "میکروفون پیدا نشد" in text
    assert "NotAllowedError" in text
    assert "openai/gpt-oss-120b" in text
    assert "m.type==='fatal'" in text
    assert "خطای provider" in text
