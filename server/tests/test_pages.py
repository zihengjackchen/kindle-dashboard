from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from app.config import Settings
from app.main import create_app
from app.models import DashboardRequest, PAGE_IDS
from app.renderer import render_dashboard, stamp
from app.snapshots import Snapshot, load_snapshot

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def sample():
    return Snapshot.model_validate_json((ROOT / "docs/previews/sample-snapshot.json").read_text())


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("size", [(600, 800), (1236, 1648), (1648, 1236)])
def test_pages_render_with_real_snapshot_schema(sample, page, size):
    png = render_dashboard(DashboardRequest(page=page, width=size[0], height=size[1]), Settings(), snapshot=sample)
    with Image.open(BytesIO(png)) as image:
        image.load()
        assert image.size == size and image.mode == "L"
        assert image.getextrema() == (0, 255)


def test_api_page_acknowledgement():
    client = TestClient(create_app(Settings()))
    for page in PAGE_IDS:
        response = client.get("/dashboard.png", params={"page": page})
        assert response.status_code == 200
        assert response.headers["x-dashboard-page"] == page
    assert client.get("/dashboard.png?page=../../private").status_code == 422


def test_freshness_does_not_follow_render_time(sample):
    weather = sample.weather
    assert weather.status(weather.as_of) == "CURRENT"
    assert weather.status(weather.valid_until + timedelta(seconds=1)) == "STALE"
    assert weather.status(weather.as_of - timedelta(seconds=1)) == "CHECK TIME"
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    before = weather.as_of
    render_dashboard(DashboardRequest(), Settings(), now, snapshot=sample)
    assert weather.as_of == before
    # Visible dates must be absolute and unambiguous even in a months-old cache.
    assert stamp(weather, now, timezone.utc) == "STALE / 2026-10-01 16:35 UTC / Design sample"


def test_missing_invalid_and_oversized_snapshot(tmp_path):
    assert load_snapshot("").quotes == []
    path = tmp_path / "snapshot.json"
    assert load_snapshot(str(path)).weather is None
    path.write_text('{"quotes": "bad"}')
    assert load_snapshot(str(path)).quotes == []
    path.write_bytes(b"x" * 262145)
    assert load_snapshot(str(path)).weather is None


def test_reject_ambiguous_or_invalid_quotes(sample):
    raw = sample.model_dump(mode="json")
    raw["quotes"][0]["as_of"] = "2026-10-01T16:35:00"  # no timezone
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
    raw = sample.model_dump(mode="json")
    raw["quotes"][0]["price"] = float("nan")
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
    raw = sample.model_dump(mode="json")
    raw["quotes"][0]["basis"] = "24h"
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
    raw = sample.model_dump(mode="json")
    raw["quotes"][1] = raw["quotes"][0]
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)


def test_publish_preserves_previous_snapshot_on_invalid_input(tmp_path, sample):
    source = tmp_path / "incoming.json"
    output = tmp_path / "snapshot.json"
    source.write_text(sample.model_dump_json())
    command = [sys.executable, str(ROOT / "scripts/publish-snapshot.py"), str(source), "--output", str(output)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    original = output.read_bytes()
    assert json.loads(original)["demo"] is True
    source.write_text("not-json")
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == original
