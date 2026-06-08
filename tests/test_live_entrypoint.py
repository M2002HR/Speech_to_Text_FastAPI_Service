from api.app.main_live import app


def test_main_live_registers_websocket_route():
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/live" in paths
    assert "/live/ws" in paths
