import base64
from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import pytest

from app.config import Settings
from app.main import create_app
from app.markdown_widget import measure
from app.reports import Report, ReportStore, paginate, render_report


def archive(path, day="2026-11-02", text="**A report**\n\nKeep **every** condition.\n\n" * 60):
    value = {"local_date": day, "created_at": day + "T16:00:00+00:00", "content": text}
    (path / (day + ".json")).write_text(json.dumps(value), encoding="utf-8")
    return value


def test_archive_exact_content_and_last_good_fallback(tmp_path):
    value = archive(tmp_path)
    store = ReportStore(str(tmp_path))
    assert store.get().content == value["content"]
    (tmp_path / "2026-11-03.json").write_text('{"content":"incomplete"}')
    assert store.get().day == "2026-11-02"
    (tmp_path / "2026-11-02.json").unlink()
    assert store.get().content == value["content"]
    assert ReportStore(str(tmp_path)).get() is None


@pytest.mark.parametrize("width,height", [(600, 800), (1056, 1162), (1648, 1236)])
def test_paginated_grayscale_images_and_complete_text(width, height):
    source = "# Heading\n\n" + "A condition **must survive**; *italics* and [link label](https://invalid.test).\n" * 80
    report = Report("2026-11-02", "", source)
    images = render_report(report, width, height)
    assert len(images) > 1
    for png in images:
        image = Image.open(BytesIO(png)); image.load()
        assert image.mode == "L" and image.size == (width, height)
    rows = measure(ImageDraw.Draw(Image.new("L", (1, 1))), source, width-40, 26, "")
    pages = paginate(rows, height-80)
    text_before = "".join(run[1] for line, _ in rows for run in line)
    text_after = "".join(run[1] for page in pages for line, _ in page for run in line)
    assert text_after == text_before
    assert "**" not in text_after and "*italics*" not in text_after
    assert text_after.count("must survive") == 80
    assert all(sum(h for _, h in page) <= height-80 for page in pages)


def test_report_bundle_and_authenticated_preview(tmp_path):
    archive(tmp_path)
    layout = tmp_path / "layout.json"
    layout.write_text(json.dumps({"report_enabled": True, "page_order": ["overview"]}))
    client = TestClient(create_app(Settings(api_token="test", report_directory=str(tmp_path), layout_path=str(layout))))
    auth = {"Authorization": "Bearer test"}
    assert client.get('/report.png').status_code == 401
    preview = client.get('/report.png?width=1056&height=1162&number=2&font_size=30', headers=auth)
    assert preview.status_code == 200, preview.text
    assert int(preview.headers['x-report-pages']) > 1
    assert preview.headers['cache-control'] == 'no-store'
    assert client.get('/report.png?number=0', headers=auth).status_code == 422
    assert client.get('/report.png?font_size=4', headers=auth).status_code == 422
    assert client.get('/report.png?number=27', headers=auth).status_code == 404
    result = client.get('/dashboard-bundle.json?width=1056&height=1162', headers=auth)
    assert result.status_code == 200
    data = result.json()
    ids = [page['id'] for page in data['settings']['pages']]
    assert ids[0] == 'overview' and ids[1:] == [f'report-{i}' for i in range(1, len(ids))]
    assert base64.b64decode(data['images']['report-2']) == preview.content
    # No report pages unless explicitly enabled in the saved layout.
    client = TestClient(create_app(Settings(report_directory=str(tmp_path))))
    assert len(client.get('/dashboard-bundle.json').json()['images']) == 5


def test_limits_fail_instead_of_truncating():
    with pytest.raises(ValueError, match="27 pages"):
        paginate([([('text',)], 20)] * 28, 20)
