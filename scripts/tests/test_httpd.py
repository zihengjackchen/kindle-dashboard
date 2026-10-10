"""Regression coverage for Kindles whose stock BusyBox lacks httpd."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile

import pytest
from test_client import SH, EXT, nas, setup  # noqa: F401


def select(setup, body):
    env, *_ = setup
    return subprocess.run([SH, "-c", '. "$DASHBOARD_DIR/lib/client.sh"; '
                          '. "$DASHBOARD_DIR/lib/httpd.sh"; ' + body],
                          env=env, capture_output=True, text=True, timeout=15)


def helper(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nprintf '%s\\n' '" + text + "'\n", encoding="ascii")
    path.chmod(0o755)


def test_private_helper_preferred_when_stock_has_no_httpd(setup):
    _, data, *_ = setup
    helper(data / "bin/busybox", "Usage: httpd -f -p PORT -h HOME")
    helper(data / "stock/busybox", "httpd: applet not found")
    result = select(setup, f'PATH="$(cd "{data.as_posix()}/stock" && pwd):$PATH"; '
                    f'DASHBOARD_DIR="{data.as_posix()}"; BUSYBOX_BIN=auto; '
                    'select_httpd && printf "SELECTED=%s" "$HTTPD_BIN"')
    assert result.returncode == 0, result.stderr
    assert "SELECTED=" + (data / "bin/busybox").as_posix() in result.stdout


def test_missing_httpd_fails_with_readable_probe(setup):
    _, data, *_ = setup
    helper(data / "stock-busybox", "httpd: applet not found")
    result = select(setup, f'BUSYBOX_BIN="{data.as_posix()}/stock-busybox"; select_httpd')
    assert result.returncode != 0
    assert "applet not found" in (data / "logs/httpd-probe.txt").read_text()
    assert "No compatible HTTP helper" in (data / "logs/dashboard.log").read_text()


def test_loader_failure_recorded_and_falls_back(setup):
    _, data, *_ = setup
    helper(data / "bin/busybox", "error while loading shared libraries")
    helper(data / "stock/busybox", "Usage: httpd -f -p PORT -h HOME")
    result = select(setup, f'PATH="$(cd "{data.as_posix()}/stock" && pwd):$PATH"; '
                    f'DASHBOARD_DIR="{data.as_posix()}"; BUSYBOX_BIN=auto; '
                    'select_httpd && printf "SELECTED=%s" "$HTTPD_BIN"')
    assert result.returncode == 0, result.stderr
    assert "SELECTED=busybox" in result.stdout
    assert "shared libraries" in (data / "logs/httpd-probe.txt").read_text()


def test_launch_failure_leaves_notice_and_no_session(setup):
    env, data, *_ = setup
    for name in ("sqlite3", "lipc-get-prop", "lipc-set-prop", "mesquite"):
        helper(data / "stock" / name, "unexpected command execution")
    helper(data / "stock/busybox", "httpd: applet not found")
    body = (f'PATH="$(cd "{data.as_posix()}/stock" && pwd):$PATH"; export PATH; '
            f'BUSYBOX_BIN="{data.as_posix()}/stock/busybox"; export BUSYBOX_BIN; '
            f'exec sh "{(EXT / "app-launch.sh").as_posix()}"')
    result = subprocess.run([SH, "-c", body], env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    log = (data / "logs/dashboard.log").read_text()
    assert "MOCK notice: Dashboard could not start" in log
    assert "No compatible HTTP helper" in log
    assert "No compatible HTTP helper" in (data / "logs/startup.log").read_text()
    assert not (data / "state/app.pid").exists()


def preparer():
    spec = importlib.util.spec_from_file_location("prepare_httpd", Path(__file__).parents[1] / "prepare-httpd.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bad_download_never_installs(tmp_path):
    module = preparer()
    with pytest.raises(ValueError, match="checksum"):
        module.prepare(b"error page", tmp_path / "bin")
    assert not (tmp_path / "bin").exists()


def test_extracts_only_verified_helper(tmp_path, monkeypatch):
    module = preparer()
    binary = b"\x7fELF\x01\x01\x01" + b"\0" * 11 + b"\x28\x00"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as archive:
        for name, content in [(module.MEMBER, binary), ("USBNetwork/README", b"credits"),
                              ("../../unwanted", b"installer")]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    data = buf.getvalue()
    monkeypatch.setattr(module, "ARCHIVE_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(module, "BINARY_SHA256", hashlib.sha256(binary).hexdigest())
    module.prepare(data, tmp_path / "bin")
    assert (tmp_path / "bin/busybox").read_bytes() == binary
    assert sorted(p.name for p in (tmp_path / "bin").iterdir()) == ["PROVENANCE.txt", "busybox", "upstream-README.txt"]
    assert not (tmp_path / "unwanted").exists()
