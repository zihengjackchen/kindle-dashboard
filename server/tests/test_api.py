from datetime import datetime, timezone
from io import BytesIO
import base64

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.models import DashboardRequest
from app.renderer import render_dashboard


@pytest.fixture
def client():
    return TestClient(create_app(Settings()))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("width,height", [(600, 800), (1056, 1140)])
def test_bundle_contains_all_pages_and_settings(client, width, height):
    response = client.get(f"/dashboard-bundle.json?width={width}&height={height}&battery=73&charging=1")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    assert response.headers['cache-control'] == 'no-store'
    bundle = response.json()
    assert bundle['version'] == 1 and bundle['battery'] == 73 and bundle['charging']
    assert len(bundle['images']) == 5
    assert set(bundle['images']) == {p['id'] for p in bundle['settings']['pages']}
    for image in bundle['images'].values():
        with Image.open(BytesIO(base64.b64decode(image, validate=True))) as decoded:
            decoded.load()
            assert decoded.size == (width, height) and decoded.mode == 'L'


def test_bundle_auth_validation_and_failure(monkeypatch):
    client = TestClient(create_app(Settings(api_token='secret')))
    assert client.get('/dashboard-bundle.json').status_code == 401
    headers = {'Authorization': 'Bearer secret'}
    assert client.get('/dashboard-bundle.json?battery=101', headers=headers).status_code == 422
    def broken(*args):
        raise RuntimeError('render failed')
    monkeypatch.setattr('app.main.render_dashboard', broken)
    response = client.get('/dashboard-bundle.json', headers=headers)
    assert response.status_code == 500
    assert 'images' not in response.json()


@pytest.mark.parametrize("width,height", [(600, 800), (758, 1024), (1072, 1448), (1236, 1648), (1648, 1236), (320, 320), (2560, 2560)])
def test_image_dimensions_and_headers(client, width, height):
    response = client.get("/dashboard.png", params={"width": width, "height": height, "battery": 73, "charging": 0})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(response.content)) as image:
        image.load()
        assert image.size == (width, height)
        assert image.mode == "L"
        assert image.getextrema() == (0, 255)


def test_missing_parameters(client):
    response = client.get("/dashboard.png")
    assert response.status_code == 200
    assert Image.open(BytesIO(response.content)).size == (1236, 1648)
    assert DashboardRequest().battery is None
    assert DashboardRequest().charging is None


@pytest.mark.parametrize("name,value", [("width", 0), ("height", -1), ("width", "oops"), ("height", "1.5"), ("width", 100001), ("battery", -1), ("battery", 101), ("battery", "invalid"), ("charging", 2), ("charging", "maybe"), ("device", "x" * 81), ("device", "bad\nname")])
def test_invalid_parameters(client, name, value):
    assert client.get("/dashboard.png", params={name: value}).status_code == 422


def test_dimensions_are_clamped(client):
    response = client.get("/dashboard.png?width=1&height=9999")
    assert response.status_code == 200
    assert Image.open(BytesIO(response.content)).size == (320, 2560)


@pytest.mark.parametrize("charging", ["0", "1", "true", "false"])
def test_charging_values(client, charging):
    assert client.get("/dashboard.png", params={"charging": charging}).status_code == 200


@pytest.mark.parametrize("battery", [0, 100])
def test_battery_boundaries(client, battery):
    assert client.get("/dashboard.png", params={"battery": battery}).status_code == 200


def test_authentication():
    client = TestClient(create_app(Settings(api_token="test-token")))
    assert client.get("/health").status_code == 200
    assert client.get("/dashboard.png").status_code == 401
    assert client.get("/dashboard.png", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/dashboard.png", headers={"Authorization": "Bearer test-token"}).status_code == 200


def test_generation_failure(client, monkeypatch, caplog):
    def broken(*args):
        raise RuntimeError("test render failure")
    monkeypatch.setattr("app.main.render_dashboard", broken)
    response = client.get("/dashboard.png")
    assert response.status_code == 500
    assert response.json() == {"detail": "Image generation failed"}
    assert "PNG generation failed" in caplog.text


def test_renderer_deterministic():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    args = (DashboardRequest(battery=73, charging=False), Settings(), now)
    assert render_dashboard(*args) == render_dashboard(*args)
