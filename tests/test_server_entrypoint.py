from fastapi.testclient import TestClient

from api.app.server import app


def _base_routes(application):
    base = getattr(application, "base", application)
    return [getattr(route, "path", "") for route in base.router.routes]


def test_server_exposes_all_service_paths():
    paths = _base_routes(app)
    # Base transcription API + web panels
    assert "/health" in paths
    assert "/providers" in paths
    assert "/transcribe" in paths
    # Realtime streaming
    assert "/realtime" in paths
    assert "/ws/realtime" in paths


def test_server_providers_route_is_not_broken_by_deepgram_override():
    # Regression: the Deepgram /providers override used an un-annotated
    # `request` param, which FastAPI treated as a query field (HTTP 422).
    with TestClient(app) as client:
        resp = client.get("/providers")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        names = {p["name"] for p in body["providers"]}
        assert {"local", "openai", "groq", "deepgram", "custom"} <= names


def test_server_serves_live_and_realtime_panels():
    with TestClient(app) as client:
        assert client.get("/live").status_code == 200
        assert client.get("/realtime").status_code == 200
