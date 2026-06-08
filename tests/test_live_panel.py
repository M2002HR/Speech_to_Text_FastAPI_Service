from pathlib import Path

from api.app.main import app


def test_live_panel_routes_are_registered():
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/live" in paths
    assert "/live/ws" in paths


def test_live_panel_file_exists():
    live_html = Path(__file__).resolve().parents[1] / "api" / "app" / "ui" / "live.html"
    text = live_html.read_text(encoding="utf-8")
    assert "Tootak Live" in text
    assert "/live/ws" in text
    assert "VAD" in text
    assert "skippedCount" in text
