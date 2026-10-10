"""Real shell + real HTTP, with only framebuffer/device access mocked."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
EXT = ROOT / "kindle-client/extensions/dashboard"
SH = os.getenv("TEST_SHELL") or shutil.which("sh")
if not SH and os.name == "nt":
    candidate = Path("C:/Program Files/Git/usr/bin/sh.exe")
    if candidate.exists():
        SH = str(candidate)
pytestmark = pytest.mark.skipif(not SH, reason="POSIX sh required (Git Bash also works)")


@pytest.fixture
def nas():
    api = TestClient(create_app(Settings(api_token="test-secret")))
    received = []
    entered = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            received.append((self.path, self.headers.get("Authorization")))
            path = urlsplit(self.path).path
            if path == "/slow":
                entered.set()
                time.sleep(2)
            if path == "/error":
                code, mime, content = 500, "text/html", b"server error"
            elif path == "/html":
                code, mime, content = 200, "image/png", b"<html>Not a PNG</html>"
            else:
                endpoint = "/dashboard-bundle.json" if path == "/dashboard-bundle.json" else "/dashboard.png"
                response = api.get(endpoint + "?" + urlsplit(self.path).query, headers={"Authorization": self.headers.get("Authorization", "")})
                code, mime, content = response.status_code, response.headers["content-type"], response.content
                if path == "/truncated":
                    content = content[:-8]
                if path == "/wrong-size":
                    content = api.get("/dashboard.png?width=758&height=1024", headers={"Authorization": "Bearer test-secret"}).content
                if path == "/wrong-mime":
                    mime = "text/html"
                if path == "/redirect":
                    code = 302
                if path == "/oversize":
                    content = b"x" * (1024 * 1024)
            try:
                self.send_response(code)
                self.send_header("Content-Type", mime)
                self.send_header("X-Dashboard-Page", parse_qs(urlsplit(self.path).query).get("page", ["overview"])[0])
                self.send_header("Content-Length", str(len(content)))
                if path == "/redirect":
                    self.send_header("Location", "/dashboard.png")
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", received, entered
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def setup(tmp_path, nas):
    base, received, entered = nas
    env = os.environ.copy()
    if os.name == "nt":
        git_root = Path(SH).parents[2]
        env["PATH"] = str(git_root / "usr/bin") + os.pathsep + str(git_root / "mingw64/bin") + os.pathsep + env.get("PATH", "")
    env.update(MOCK_MODE="1", MOCK_WIDTH="600", MOCK_HEIGHT="800", API_TOKEN="test-secret",
               DASHBOARD_DATA_DIR=tmp_path.as_posix(), DISABLE_FILE=(tmp_path / "dashboard-disable").as_posix(),
               DASHBOARD_URL=base + "/dashboard.png", DASHBOARD_DIR=EXT.as_posix(), HTTP_CLIENT="curl",
               KUAL_SETTLE_SECONDS="0", DOWNLOAD_TIMEOUT_SECONDS="5", CONNECT_TIMEOUT_SECONDS="2")
    return env, tmp_path, base, received, entered


def run(env, script="refresh-once.sh", body=None):
    args = [SH, (EXT / script).as_posix()] if body is None else [SH, "-c", body]
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)


def log(data):
    return (data / "logs/dashboard.log").read_text()


def test_live_service_refresh_and_start_stop(setup):
    env, data, _, received, _ = setup
    result = run(env)
    assert result.returncode == 0, result.stderr
    assert (data / "cache/dashboard.png").read_bytes().startswith(b"\x89PNG")
    params = parse_qs(urlsplit(received[0][0]).query)
    assert params["battery"] == ["73"] and params["charging"] == ["0"]
    assert params["width"] == ["600"] and params["height"] == ["800"]
    assert received[0][1] == "Bearer test-secret"
    assert "MOCK display command:" in log(data)
    assert "test-secret" not in log(data)
    assert not (data / "state/active").exists()
    assert run(env, "start.sh").returncode == 0
    assert (data / "state/active").exists()
    Path(env["DISABLE_FILE"]).touch()
    assert run(env, "stop.sh").returncode == 0
    assert not (data / "state/active").exists()
    assert (data / "cache/dashboard.png").exists()
    assert not (data / "state/action.lock").exists()
    assert not list((data / "cache").glob("*.tmp.*"))


@pytest.mark.parametrize("endpoint", ["error", "html", "truncated", "wrong-size", "wrong-mime", "redirect", "oversize"])
def test_failure_retains_previous_cache(setup, endpoint):
    env, data, base, _, _ = setup
    assert run(env).returncode == 0
    original = (data / "cache/dashboard.png").read_bytes()
    env.update(DASHBOARD_URL=base + "/" + endpoint, MAX_IMAGE_BYTES="65536")
    assert run(env).returncode != 0
    assert (data / "cache/dashboard.png").read_bytes() == original
    assert "Retained and displayed previous cache" in log(data)
    assert not list((data / "cache").glob("*.tmp.*"))


def test_no_cache_failure_and_auth(setup):
    env, data, _, _, _ = setup
    env["API_TOKEN"] = "wrong-secret"
    assert run(env, "start.sh").returncode != 0
    assert not (data / "state/active").exists()
    assert not (data / "cache/dashboard.png").exists()
    assert "wrong-secret" not in log(data)


def test_unknown_telemetry_is_omitted(setup):
    env, _, _, received, _ = setup
    env.update(MOCK_BATTERY="unknown", MOCK_CHARGING="unknown")
    assert run(env).returncode == 0
    query = parse_qs(urlsplit(received[0][0]).query)
    assert "battery" not in query and "charging" not in query


def test_telemetry_reports_previous_result_and_battery_samples(setup):
    env, data, base, received, _ = setup
    env.update(DEVICE_ID="bedside", MOCK_RSSI="-61")
    assert run(env).returncode == 0
    query = parse_qs(urlsplit(received[-1][0]).query)
    assert query["device_id"] == ["bedside"] and query["rssi"] == ["-61"]
    assert "last_success_epoch" not in query
    env["DASHBOARD_URL"] = base + "/error"
    assert run(env).returncode != 0
    env["DASHBOARD_URL"] = base + "/dashboard.png"
    assert run(env).returncode == 0
    query = parse_qs(urlsplit(received[-1][0]).query)
    assert query["fetch_failures"] == ["1"]
    assert int(query["last_success_epoch"][0]) > 0
    assert (data / "state/fetch_failures").read_text().strip() == "0"
    count = len(received)
    assert run(env, "sample-battery.sh").returncode == 0
    assert len(received) == count
    assert ",manual" in (data / "logs/battery.csv").read_text()
    env["SEND_TELEMETRY"] = "0"
    assert run(env).returncode == 0
    query = parse_qs(urlsplit(received[-1][0]).query)
    assert "device_id" not in query and "rssi" not in query


def test_kill_switch_and_unverified_power(setup):
    env, data, _, received, _ = setup
    Path(env["DISABLE_FILE"]).touch()
    assert run(env, "start.sh").returncode != 0
    assert not received
    Path(env["DISABLE_FILE"]).unlink()
    env["ENABLE_EXPERIMENTAL_POWER"] = "1"
    assert run(env, "start.sh").returncode != 0
    assert not received
    assert not (data / "state/active").exists()


def test_kill_switch_during_fetch(setup):
    env, data, base, _, entered = setup
    env["DASHBOARD_URL"] = base + "/slow"
    process = subprocess.Popen([SH, (EXT / "start.sh").as_posix()], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert entered.wait(8)
    Path(env["DISABLE_FILE"]).touch()
    process.communicate(timeout=10)
    assert process.returncode != 0
    assert "MOCK display command" not in log(data)
    assert not (data / "state/active").exists()


def test_total_timeout_and_lock(setup):
    env, data, base, _, entered = setup
    env.update(DASHBOARD_URL=base + "/slow", DOWNLOAD_TIMEOUT_SECONDS="1")
    process = subprocess.Popen([SH, (EXT / "refresh-once.sh").as_posix()], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert entered.wait(8)
    result = run(env)
    assert result.returncode != 0 and "lock" in result.stderr
    process.communicate(timeout=10)
    assert process.returncode != 0
    assert not (data / "state/action.lock").exists()


def test_display_failure_rolls_back_cache(setup):
    env, data, _, _, _ = setup
    assert run(env).returncode == 0
    original = (data / "cache/dashboard.png").read_bytes()
    env["MOCK_BATTERY"] = "42"
    result = run(env, body=' . "$DASHBOARD_DIR/lib/client.sh"; acquire_lock || exit 1; display_image() { return 1; }; refresh_dashboard')
    assert result.returncode != 0
    assert (data / "cache/dashboard.png").read_bytes() == original
    assert "rolling back cache" in log(data)


def test_signal_rolls_back_pending_draw_and_start(setup):
    env, data, _, _, _ = setup
    assert run(env).returncode == 0
    original = (data / "cache/dashboard.png").read_bytes()
    env["MOCK_BATTERY"] = "42"
    body = '''
    . "$DASHBOARD_DIR/lib/client.sh"
    acquire_lock || exit 1
    START_PENDING=1
    printf 'starting\n' > "$STATE_DIR/active"
    display_image() { kill -TERM "$$"; }
    refresh_dashboard
    '''
    assert run(env, body=body).returncode != 0
    assert (data / "cache/dashboard.png").read_bytes() == original
    assert not (data / "state/active").exists()
    assert not (data / "state/action.lock").exists()


def test_eips_mock_backend(setup):
    env, data, _, _, _ = setup
    env["DISPLAY_BACKEND"] = "eips"
    assert run(env).returncode == 0
    assert "MOCK display command: eips -f -g" in log(data)


def test_gnu_wget_when_installed(setup):
    env, data, _, received, _ = setup
    check = subprocess.run([SH, "-c", "wget --help"], env=env, capture_output=True, text=True)
    if check.returncode != 0 or "--max-redirect" not in check.stdout:
        pytest.skip("GNU wget with redirect controls not installed")
    env["HTTP_CLIENT"] = "wget"
    assert run(env).returncode == 0
    assert received[0][1] == "Bearer test-secret"
    assert (data / "cache/dashboard.png").read_bytes().startswith(b"\x89PNG")


def test_rotation_and_diagnostics(setup):
    env, data, _, _, _ = setup
    env["MAX_LOG_BYTES"] = "1024"
    (data / "logs").mkdir()
    (data / "logs/dashboard.log").write_text("x" * 1024)
    assert run(env, "diagnostics.sh").returncode == 0
    assert (data / "logs/dashboard.log.1").exists()
    report = (data / "logs/diagnostics.txt").read_text()
    assert "Normalized detection" in report
    assert "test-secret" not in report
    assert (data / "logs/diagnostics.txt").stat().st_size <= 65536


def test_shell_syntax_and_kual_structure():
    for path in EXT.rglob("*.sh"):
        assert b"\r\n" not in path.read_bytes()
        result = subprocess.run([SH, "-n", str(path)], capture_output=True)
        assert result.returncode == 0, path
    menu = json.loads((EXT / "menu.json").read_text())
    assert len(menu["items"][0]["items"]) == 8


def test_battery_parsing_and_eips_geometry(setup):
    env, _, _, _, _ = setup
    body = '''
    . "$DASHBOARD_DIR/lib/client.sh"
    [ "$(battery_percent '73%')" = 73 ] || exit 1
    [ "$(battery_percent '0')" = 0 ] || exit 1
    battery_percent 101 && exit 1
    battery_percent -1 && exit 1
    [ "$(charging_value Full)" = 0 ] || exit 1
    [ "$(charging_value Charging)" = 1 ] || exit 1
    FBINK_BIN=missing-fbink
    EIPS_BIN=printf
    probe() { printf 'xres: 600\nyres: 800\nxres_virtual: 600\nyres_virtual: 1600\n'; }
    [ "$(display_geometry)" = '600 800' ]
    '''
    assert run(env, body=body).returncode == 0


def test_offline_carousel_and_page_caches(setup):
    env, data, base, received, _ = setup
    assert run(env, "refresh-pages.sh").returncode == 0
    assert len(received) == 5
    assert len(list((data / "cache/pages").glob("*.png"))) == 5
    env["DASHBOARD_URL"] = base + "/error"
    for page in ("weather", "markets-1", "markets-2", "nas", "overview"):
        assert run(env, "page.sh").returncode == 0
        assert (data / "state/current-page").read_text().strip() == page
        assert (data / "cache/dashboard.png").read_bytes() == (data / f"cache/pages/{page}.png").read_bytes()
    assert len(received) == 5, "Page navigation must not request the NAS"


def test_native_event_state_machine(setup):
    env, data, _, received, _ = setup
    body = '''
    . "$DASHBOARD_DIR/lib/client.sh"
    session_token=test-session
    wake_sequence=0
    queue_restore() { printf '%s\n' "$1" >> "$STATE_DIR/queued"; }
    touch "$STATE_DIR/active"
    printf unlocked > "$STATE_DIR/mock-lock"
    printf active > "$STATE_DIR/native-phase"
    handle_native_event exitingScreenSaver
    [ ! -e "$STATE_DIR/queued" ] || exit 1
    handle_native_event goingToScreenSaver
    handle_native_event outOfScreenSaver
    [ "$(cat "$STATE_DIR/native-phase")" = locked ] || exit 1
    [ ! -e "$STATE_DIR/queued" ] || exit 1
    printf locked > "$STATE_DIR/mock-lock"
    handle_native_event exitingScreenSaver
    [ ! -e "$STATE_DIR/queued" ] || exit 1
    printf unlocked > "$STATE_DIR/mock-lock"
    handle_native_event exitingScreenSaver
    handle_native_event exitingScreenSaver
    [ "$(wc -l < "$STATE_DIR/queued")" -eq 1 ] || exit 1
    handle_native_event readyToSuspend
    [ ! -e "$STATE_DIR/wake-ticket" ] || exit 1
    [ "$(cat "$STATE_DIR/native-phase")" = sleeping ]
    '''
    assert run(env, body=body).returncode == 0
    assert not received


@pytest.mark.parametrize("block", ["none", "locked", "sleep", "stopped", "disabled", "stale-ticket"])
def test_wake_worker_is_offline_and_fail_closed(setup, block):
    env, data, _, received, _ = setup
    assert run(env, "start.sh").returncode == 0
    env.update(WAKE_RESTORE="1", WAKE_SETTLE_SECONDS="0")
    state = data / "state"
    for file, value in {"mock-lock": "unlocked", "native-phase": "restoring", "session-token": "test-session", "wake-ticket": "test-session.1"}.items():
        (state / file).write_text(value)
    if block == "locked": (state / "mock-lock").write_text("locked")
    if block == "sleep": (state / "native-phase").write_text("sleeping")
    if block == "stopped": (state / "active").unlink()
    if block == "disabled": Path(env["DISABLE_FILE"]).touch()
    if block == "stale-ticket": (state / "wake-ticket").write_text("test-session.2")
    original = (data / "cache/dashboard.png").read_bytes()
    result = run(env, body='sh "$DASHBOARD_DIR/restore-on-wake.sh" test-session test-session.1')
    assert (result.returncode == 0) == (block == "none"), result.stderr
    assert len(received) == 1
    assert (data / "cache/dashboard.png").read_bytes() == original
    assert ("Wake restore: cached image displayed" in log(data)) == (block == "none")


def test_sleep_cancels_restore_during_settle(setup):
    env, data, _, received, _ = setup
    assert run(env, "start.sh").returncode == 0
    env.update(WAKE_RESTORE="1", WAKE_SETTLE_SECONDS="2")
    for file, value in {"mock-lock": "unlocked", "native-phase": "restoring", "session-token": "test-session", "wake-ticket": "test-session.1"}.items():
        (data / "state" / file).write_text(value)
    process = subprocess.Popen([SH, (EXT / "restore-on-wake.sh").as_posix(), "test-session", "test-session.1"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(.4)
    (data / "state/native-phase").write_text("sleeping")
    (data / "state/wake-ticket").unlink()
    process.communicate(timeout=8)
    assert process.returncode != 0
    assert len(received) == 1
    assert "Wake restore: cached image displayed" not in log(data)


def test_blocking_listener_start_restore_and_stop(setup):
    env, data, _, received, _ = setup
    (data / "state").mkdir()
    (data / "state/mock-lock").write_text("unlocked")
    source = data / "fake-lipc"
    source.write_text('''#!/bin/sh
printf 'goingToScreenSaver 2\noutOfScreenSaver 1\nexitingScreenSaver\n'
exec sleep 30
''', newline="\n")
    source.chmod(0o755)
    env.update(WAKE_RESTORE="1", WAKE_SETTLE_SECONDS="0", LIPC_WAIT_BIN=source.as_posix())
    assert run(env, "start.sh").returncode == 0
    listener_pid = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and "Wake restore: cached image displayed" not in log(data):
            time.sleep(.1)
        assert "Wake restore: cached image displayed" in log(data), log(data)
        assert len(received) == 1
        listener_pid = (data / "state/listener.pid").read_text().strip()
    finally:
        assert run(env, "stop.sh").returncode == 0
    assert not (data / "state/session-token").exists()
    assert not (data / "state/active").exists()
    if listener_pid:
        env["TEST_LISTENER_PID"] = listener_pid
        # Verify Stop actually ends the process, not merely its state marker.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            check = subprocess.run([SH, "-c", 'test -r "/proc/$TEST_LISTENER_PID/cmdline" && tr "\\000" "\\n" < "/proc/$TEST_LISTENER_PID/cmdline"'], env=env, capture_output=True, text=True)
            if "wake-listener.sh" not in check.stdout:
                break
            time.sleep(.1)
        assert "wake-listener.sh" not in check.stdout
