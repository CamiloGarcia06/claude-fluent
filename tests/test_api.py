"""Humo de la API sin Anki ni modelo: lo que se puede comprobar en frío."""

from fastapi.testclient import TestClient

from fluent import main as app_module


def client() -> TestClient:
    return TestClient(app_module.app)


def test_health_without_anki(monkeypatch):
    monkeypatch.setattr(app_module.app.state.anki, "is_alive", lambda: False)
    body = client().get("/api/health").json()
    assert body["anki"] is False
    assert set(body) == {"anki", "claude", "last_sync", "syllabus"}
    assert body["syllabus"] == {"total": 0, "unreadable": []}


def test_settings_round_trip_and_validation():
    c = client()
    assert c.get("/api/settings").json() == {"daily_goal": 40}
    assert c.post("/api/settings", json={"daily_goal": 25}).json() == {"daily_goal": 25}
    assert c.get("/api/settings").json() == {"daily_goal": 25}
    assert c.post("/api/settings", json={"daily_goal": 1}).status_code == 400
    assert c.post("/api/settings", json={"daily_goal": "x"}).status_code == 400
    assert app_module.app.state.settings.read()["daily_goal"] == 25


def test_today_is_503_without_anki(monkeypatch):
    monkeypatch.setattr(app_module.app.state.anki, "is_alive", lambda: False)
    assert client().get("/api/today").status_code == 503


def test_static_ui_is_served():
    r = client().get("/")
    assert r.status_code == 200 and "fluent test" in r.text
