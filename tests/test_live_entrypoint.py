from fastapi.testclient import TestClient

from api.app.main_live import app


def test_main_live_exposes_live_paths():
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/live" in paths
    assert "/live/ws" in paths


def test_main_live_websocket_accepts_connection():
    with TestClient(app) as client:
        with client.websocket_connect("/live/ws") as ws:
            ws.send_json({
                "type": "start",
                "provider": "local",
                "stt_model": "tiny",
                "language": "auto",
                "llm_enabled": False,
                "mime_type": "audio/webm",
            })
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            ws.send_json({"type": "stop"})
