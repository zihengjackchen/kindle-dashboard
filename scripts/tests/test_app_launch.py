"""Launcher handoff regression: closing the caller must precede native startup."""
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

from test_client import SH, EXT


def test_document_caller_returns_before_native_start(tmp_path):
    extension = tmp_path / 'extension'
    (extension / 'lib').mkdir(parents=True)
    (extension / 'logs').mkdir()
    (extension / 'app-launch.sh').write_bytes((EXT / 'app-launch.sh').read_bytes())
    # Only device dependencies are mocked. Execute the real launcher twice:
    # foreground caller, then its detached child, against simulated appmgr state.
    (extension / 'lib/client.sh').write_text('''
LOG_DIR="$DASHBOARD_DIR/logs"
MAX_LOG_BYTES=65536
KUAL_SETTLE_SECONDS=0
check_enabled() { return 0; }
log() { printf '%s\\n' "$*" >> "$LOG_DIR/events"; }
probe() { cat "$DASHBOARD_DIR/foreground"; }
fail() { log "startup-check: $*"; }
display_notice() { :; }
select_httpd() { fail 'device boundary'; return 1; }
''', encoding='ascii', newline='\n')
    (extension / 'lib/httpd.sh').write_text('', encoding='ascii')
    foreground = extension / 'foreground'
    foreground.write_text('com.notmarek.shell_integration.launcher', encoding='ascii')
    env = os.environ.copy()
    env['PATH'] = str(Path(SH).parent) + os.pathsep + env['PATH']
    result = subprocess.run([SH, (extension / 'app-launch.sh').as_posix()],
                            env=env, capture_output=True, text=True, timeout=2)
    assert result.returncode == 0, result.stderr
    events = extension / 'logs/events'
    time.sleep(4)
    assert 'startup-check' not in events.read_text()
    foreground.write_text('com.lab126.KPPMainApp', encoding='ascii')
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if 'startup-check' in events.read_text():
            break
        time.sleep(.1)
    assert 'startup-check' in events.read_text()


def test_enabled_native_gestures_have_api_initialized():
    root = ET.parse(EXT / 'app/config.xml').getroot()
    ns = {'w': 'http://www.w3.org/ns/widgets',
          'k': 'http://kindle.amazon.com/ns/widget-extensions'}
    gestures = root.findall('k:gestures/k:param', ns)
    if any(p.get('value') == 'yes' for p in gestures):
        enabled = root.findall('w:feature/w:param', ns)
        assert any(p.get('name') == 'gestures' and p.get('value') == 'yes' for p in enabled)
