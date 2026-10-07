from datetime import datetime, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.layout import Layout, LayoutStore, Widget
from app.main import create_app
from app.models import DashboardRequest
from app.renderer import render_dashboard
from app.snapshots import WATCHLIST

AUTH = {"Authorization": "Bearer editor-test"}


@pytest.fixture
def editor(tmp_path):
    settings = Settings(api_token="editor-test", layout_path=str(tmp_path / "layout.json"),
                        state_path=str(tmp_path / "contacts.json"))
    return TestClient(create_app(settings)), settings


def test_editor_requires_auth_and_token_configuration(editor):
    client, _ = editor
    for method, path in (("GET", "/layout"), ("PUT", "/layout"), ("POST", "/preview.png")):
        assert client.request(method, path, json={}).status_code == 401
        assert TestClient(create_app(Settings())).request(method, path, json={}).status_code == 503


def test_preview_is_ephemeral_and_save_survives_restart(editor):
    client, settings = editor
    initial = client.get("/layout", headers=AUTH).json()["layout"]
    changed = dict(initial, title="My day", widgets=[{"id": "notes", "width": "full", "size": "large"}], notes=["Coffee with Alex"])
    result = client.post("/preview.png?width=1072&height=1448&device_id=should-not-record", json=changed, headers=AUTH)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["content-type"] == "image/png"
    image = Image.open(BytesIO(result.content))
    assert image.size == (1072, 1448) and image.mode == "L"
    assert client.get("/status", headers=AUTH).json()["devices"] == {}
    assert client.get("/layout", headers=AUTH).json()["layout"] == initial
    assert client.put("/layout", json=changed, headers=AUTH).status_code == 200
    restored = TestClient(create_app(settings))
    assert restored.get("/layout", headers=AUTH).json()["layout"] == changed
    response = restored.get("/dashboard.png?width=1072&height=1448", headers=AUTH)
    assert response.status_code == 200
    assert response.content != client.post("/preview.png?width=1072&height=1448", json=initial, headers=AUTH).content


@pytest.mark.parametrize("change", [
    {"widgets": []}, {"widgets": [{"id": "weather"}, {"id": "weather"}]},
    {"widgets": [{"id": "shell"}]}, {"widgets": [{"id": "weather", "width": "huge"}]},
    {"tickers": []}, {"tickers": ["UNKNOWN"]}, {"tickers": ["VOO", "VOO"]},
    {"notes": ["a"*101]}, {"notes": ["a"]*6}, {"notes": ["a\nb"]},
    {"title": "a"*41}, {"density": "tiny"}, {"version": 2}, {"command": "no"},
])
def test_invalid_layout_never_changes_saved_preferences(editor, change):
    client, _ = editor
    original = client.get("/layout", headers=AUTH).json()["layout"]
    for method, path in (("PUT", "/layout"), ("POST", "/preview.png")):
        assert client.request(method, path, json=dict(original, **change), headers=AUTH).status_code == 422
    assert client.get("/layout", headers=AUTH).json()["layout"] == original


def test_bounded_body_and_corrupt_disk(editor, tmp_path):
    client, settings = editor
    for method, path in (("PUT", "/layout"), ("POST", "/preview.png")):
        assert client.request(method, path, content=b" "*16385, headers=AUTH).status_code == 413
        assert client.request(method, path, content=b"{broken", headers=AUTH).status_code == 422
    (tmp_path / "layout.json").write_text("{broken")
    assert LayoutStore(settings.layout_path).get() == Layout()


def test_failed_atomic_save_preserves_memory_and_disk(tmp_path, monkeypatch):
    path = tmp_path / "layout.json"
    store = LayoutStore(str(path))
    store.save(Layout(title="Original"))
    def fail(*args):
        raise OSError("Disk failure")
    monkeypatch.setattr("app.layout.os.replace", fail)
    with pytest.raises(OSError):
        store.save(Layout(title="New"))
    assert store.get().title == "Original"
    assert LayoutStore(str(path)).get().title == "Original"
    assert not list(tmp_path.glob(".layout-*"))


def test_default_overview_draws_entire_watchlist_and_hiding_works(monkeypatch):
    from app.widgets import Card
    text = []
    original = Card.text
    def record(self, value, *args, **kwargs):
        text.append(str(value))
        return original(self, value, *args, **kwargs)
    monkeypatch.setattr(Card, "text", record)
    args = (DashboardRequest(width=1072, height=1448), Settings(), datetime(2026, 10, 6, tzinfo=timezone.utc))
    render_dashboard(*args)
    assert all(symbol in text for symbol in WATCHLIST)
    text.clear()
    render_dashboard(*args, layout=Layout(widgets=[Widget(id="notes")], notes=["Lunch at noon"]))
    assert not any(symbol in text for symbol in WATCHLIST)
    assert "· Lunch at noon" in text


def test_saving_disabled_without_persistent_path():
    client = TestClient(create_app(Settings(api_token="editor-test")))
    assert client.get("/layout", headers=AUTH).json()["can_save"] is False
    assert client.put("/layout", json={}, headers=AUTH).status_code == 503


def test_extended_watchlist_dual_units_and_usage_widget():
    from app.widgets import temperatures
    from app.snapshots import SUPPORTED_SYMBOLS
    assert temperatures(32, "F") == "0°C / 32°F"
    assert temperatures(20, "C") == "20°C / 68°F"
    layout = Layout(widgets=[Widget(id="markets", width="full", size="large"), Widget(id="chatgpt")], tickers=list(SUPPORTED_SYMBOLS))
    for width, height in ((600, 800), (1072, 1448), (1648, 1236)):
        png = render_dashboard(DashboardRequest(width=width, height=height), Settings(), layout=layout)
        image = Image.open(BytesIO(png))
        assert image.size == (width, height) and image.mode == "L"
