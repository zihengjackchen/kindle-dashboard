from fastapi.testclient import TestClient
import pytest
from app.config import Settings
from app.main import create_app


def test_authenticated_contact_persists_without_counting_previews(tmp_path):
    settings = Settings(api_token="secret", state_path=str(tmp_path / "contacts.json"))
    client = TestClient(create_app(settings))
    auth = {"Authorization": "Bearer secret"}
    assert client.get("/status").status_code == 401
    assert client.get("/").status_code == 200
    assert client.get("/dashboard.png?device_id=private").status_code == 401
    assert client.get("/dashboard.png?width=320&height=320", headers=auth).status_code == 200
    assert client.get("/status", headers=auth).json()["devices"] == {}
    query = "width=320&height=320&device_id=bedside&rssi=-58&fetch_seconds=4&fetch_failures=2&last_success_epoch=1700000000"
    assert client.get("/dashboard.png?"+query, headers=auth).status_code == 200
    restored = TestClient(create_app(settings)).get("/status", headers=auth).json()
    assert restored["devices"]["bedside"]["rssi"] == -58
    assert restored["devices"]["bedside"]["fetch_failures"] == 2
    assert "last_seen" in restored["devices"]["bedside"]
    assert "secret" not in (tmp_path / "contacts.json").read_text()


@pytest.mark.parametrize("query", ["rssi=1", "rssi=-128", "fetch_seconds=-1", "fetch_failures=1000000", "device_id=../../bad", "last_success_epoch=-1"])
def test_invalid_telemetry(query):
    assert TestClient(create_app(Settings())).get("/dashboard.png?"+query).status_code == 422


def test_contact_history_is_bounded():
    from app.telemetry import ContactStore
    from app.models import DashboardRequest
    store = ContactStore()
    for i in range(40): store.contact(DashboardRequest(device_id=f"device-{i}"))
    assert len(store.snapshot()) == 32
    assert "device-0" not in store.snapshot()
