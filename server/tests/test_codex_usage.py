import importlib.util
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.config import Settings
from app.layout import Layout, Widget
from app.main import create_app
from app.models import DashboardRequest
from app.renderer import render_dashboard
from app.snapshots import CodexUsage, Snapshot, load_snapshot
from app.widgets import usage_values

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("export_usage", ROOT / "scripts/export-codex-usage.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
NOW = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)


def record():
    return exporter.usage_record(
        {"summary": {"lifetimeTokens": 500000, "currentStreakDays": 2},
         "dailyUsageBuckets": [{"startDate": "2026-10-11", "tokens": 21000}, {"startDate": "2026-10-10", "tokens": 4000}],
         "threadUsage": [{"title": "private title", "accountId": "private-account"}]},
        {"accountId": "private-account", "rateLimits": {"limitId": "codex", "limitName": "private-name",
         "primary": {"usedPercent": 11, "windowDurationMins": 10080, "resetsAt": int((NOW+timedelta(days=6)).timestamp())}}}, NOW)


def test_export_filters_private_fields_and_preserves_actual_window():
    data = record()
    usage = CodexUsage.model_validate(data)
    assert usage.primary.window_minutes == 10080 and usage.primary.used_percent == 11
    assert usage.secondary is None
    assert usage.latest_day_tokens == 21000
    assert usage.latest_day.isoformat() == "2026-10-11"
    assert "private" not in json.dumps(data)
    assert "threadUsage" not in data and "accountId" not in data
    assert usage_values(usage, NOW)["primary_remaining"] == ("7d remaining", "89%")
    assert usage_values(usage, NOW)["secondary_remaining"][1] == "Unknown"


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), True, "11"])
def test_export_rejects_invalid_percentage(value):
    with pytest.raises(ValueError):
        exporter.usage_record({}, {"rateLimits": {"primary": {"usedPercent": value}}}, NOW)


def test_unknown_counts_are_not_zero():
    value = CodexUsage.model_validate(exporter.usage_record({}, {}, NOW))
    assert value.lifetime_tokens is None and value.latest_day_tokens is None
    assert usage_values(value, NOW)["lifetime_tokens"][1] == "Unknown"


def test_source_time_and_expired_windows_are_not_refreshed_by_render():
    usage = CodexUsage.model_validate(record())
    assert usage.status(NOW) == "CURRENT"
    assert usage.status(NOW+timedelta(hours=3)) == "STALE"
    usage.primary.resets_at = NOW+timedelta(minutes=5)
    assert usage.status(NOW+timedelta(minutes=6)) == "STALE"
    assert usage_values(usage, NOW+timedelta(minutes=6))["primary_remaining"][1] == "Awaiting sync"


def test_atomic_filtered_file_and_separate_source(tmp_path, monkeypatch):
    path = tmp_path / "usage.json"
    exporter.write_atomic(path, record())
    old = path.read_bytes()
    monkeypatch.setattr(exporter.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("failure")))
    with pytest.raises(OSError):
        exporter.write_atomic(path, record())
    assert path.read_bytes() == old and not list(tmp_path.glob(".usage-*"))
    snapshot = load_snapshot("", str(path))
    assert snapshot.codex.primary.used_percent == 11
    # A malformed independent usage source cannot remove weather/market/NAS data.
    path.write_text('{"accountId":"private"}')
    assert load_snapshot("", str(path)).codex is None
    with pytest.raises(ValidationError):
        CodexUsage.model_validate({**record(), "accountId": "private"})


@pytest.mark.parametrize("size", [(600, 800), (1056, 1162), (1648, 1236)])
def test_usage_widget_renders_selectable_fields(size):
    layout = Layout(widgets=[Widget(id="codex", width="full", size="small"),
                             Widget(id="codex", key="second", fields=["lifetime_tokens", "as_of"])])
    result = render_dashboard(DashboardRequest(width=size[0], height=size[1]), Settings(), NOW,
                              Snapshot(codex=CodexUsage.model_validate(record())), layout)
    with Image.open(BytesIO(result)) as image:
        assert image.size == size and image.mode == "L"


def test_editor_and_bundle_read_same_separate_usage_source(tmp_path):
    path = tmp_path / "usage.json"
    exporter.write_atomic(path, record())
    client = TestClient(create_app(Settings(api_token="test", codex_usage_path=str(path), layout_path=str(tmp_path/"layout.json"))))
    auth = {"Authorization": "Bearer test"}
    assert client.get("/status").status_code == 401
    status = client.get("/status", headers=auth).json()
    assert status["codex"]["primary"]["used_percent"] == 11
    assert "codex" in status["sources"]
    fields = client.get("/layout", headers=auth).json()["fields"]
    assert "primary_remaining" in fields["codex"]
    assert client.put("/layout", headers=auth, json={"widgets": [{"id": "codex"}]}).status_code == 200
    assert client.get("/dashboard-bundle.json?width=600&height=800", headers=auth).status_code == 200
