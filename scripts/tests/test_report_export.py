import importlib.util
import json
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("export_stock_report", Path(__file__).resolve().parents[1] / "export_stock_report.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_only_text_exported_atomically_and_failure_retains_last_report(tmp_path):
    source, output = tmp_path / "private", tmp_path / "public"
    source.mkdir()
    text = "**Original** Markdown\n\nAll conditions and \u4e2d\u6587 preserved."
    record = dict(local_date="2026-11-02", created_at="2026-11-02T16:33:00+00:00", content=text,
                  snapshot={"private": "not-exported"}, attachment={"text": "not-exported"})
    path = source / "2026-11-02.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    owner = dict(uid=os.getuid(), gid=os.getgid()) if hasattr(os, "getuid") else {}
    assert module.export_report(source, output, **owner) == "2026-11-02"
    exported = output / path.name
    before = exported.read_bytes()
    assert json.loads(before) == {k: record[k] for k in ("local_date", "created_at", "content")}
    path.write_text('{"incomplete": true}', encoding="utf-8")
    with pytest.raises((KeyError, ValueError)):
        module.export_report(source, output, **owner)
    assert exported.read_bytes() == before
    assert not list(output.glob('.report-*'))
