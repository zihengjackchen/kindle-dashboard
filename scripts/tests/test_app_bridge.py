"""Exercise the real CGI shell against a real HTTP server, with device I/O mocked."""
import subprocess
from pathlib import Path
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
import pytest
from PIL import Image

from test_client import EXT, SH, nas, setup  # noqa: F401 -- shared fixtures


def call(env, action, key="app-test", method="POST"):
    result=subprocess.run([SH,(EXT/'app/bridge.cgi').as_posix()],
        env=dict(env,REQUEST_METHOD=method,QUERY_STRING=action,HTTP_X_DASHBOARD_SESSION=key),
        capture_output=True,timeout=20)
    assert result.returncode==0, result.stderr
    head,body=result.stdout.split(b'\r\n\r\n',1)
    return head.decode(),body


def session(setup):
    env,data,*_=setup
    (data/'state').mkdir(exist_ok=True)
    (data/'state/app-key').write_text('app-test\n')
    return env,data


def test_bridge_auth_and_action_allowlist(setup):
    env,data=session(setup)
    assert '403' in call(env,'heartbeat',key='wrong')[0]
    assert '403' in call(env,'heartbeat',method='GET')[0]
    assert b'Invalid page' in call(env,'fetch=../../config.local.sh')[1]
    assert b'Unknown action' in call(env,'command=reboot')[1]
    assert b'"ok":true' in call(env,'heartbeat')[1]
    Path(env['DISABLE_FILE']).touch()
    assert '403' in call(env,'heartbeat')[0]


def test_decode_ack_atomic_cache_and_failed_fetch(setup):
    env,data=session(setup)
    headers,png=call(env,'fetch=overview')
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    assert not (data/'cache/app/pages/overview.png').exists()
    revision=next(line.split(': ',1)[1] for line in headers.splitlines() if line.startswith('X-Dashboard-Revision'))
    assert b'Image superseded' in call(env,'commit=overview:123')[1]
    assert b'"ok":true' in call(env,'commit=overview:'+revision)[1]
    cached=(data/'cache/app/pages/overview.png').read_bytes()
    assert cached==png
    assert call(env,'cached=overview')[1]==cached
    env['DASHBOARD_URL']=setup[2]+'/html'
    headers,png=call(env,'fetch=overview')
    assert 'X-Dashboard-Stale: 1' in headers and png==cached
    assert (data/'cache/app/pages/overview.png').read_bytes()==cached
    assert 'test-secret' not in (data/'logs/dashboard.log').read_text()


def test_close_revokes_session(setup):
    env,data=session(setup)
    assert b'"ok":true' in call(env,'close')[1]
    assert not (data/'state/app-key').exists()
    assert '403' in call(env,'fetch=overview')[0]


def test_ui_entry_is_logged_only_after_authenticated_browser_call(setup):
    env, data = session(setup)
    assert '403' in call(env, 'enter', key='wrong')[0]
    logfile = data / 'logs/dashboard.log'
    assert not logfile.exists() or 'Dashboard UI connected' not in logfile.read_text()
    assert b'"ok":true' in call(env, 'enter')[1]
    assert 'Dashboard UI connected to local bridge' in logfile.read_text()


def test_viewport_render_separate_cache_and_offline_resize(setup):
    env, data = session(setup)
    panel_cache = data / 'cache/pages/overview.png'
    panel_cache.parent.mkdir(parents=True, exist_ok=True)
    Image.new('L', (600, 800), 128).save(panel_cache)
    old_panel = panel_cache.read_bytes()
    env['HTTP_X_DASHBOARD_VIEWPORT'] = '584x706'
    headers, png = call(env, 'fetch=overview')
    assert Image.open(BytesIO(png)).size == (584, 706)
    params = parse_qs(urlsplit(setup[3][-1][0]).query)
    assert params['width'] == ['584'] and params['height'] == ['706']
    revision = next(s.split(': ', 1)[1] for s in headers.splitlines() if s.startswith('X-Dashboard-Revision'))
    assert b'"ok":true' in call(env, 'commit=overview:' + revision)[1]
    assert panel_cache.read_bytes() == old_panel
    env['HTTP_X_DASHBOARD_VIEWPORT'] = '700x500'
    env['DASHBOARD_URL'] = setup[2] + '/error'
    headers, fallback = call(env, 'fetch=overview')
    assert 'X-Dashboard-Stale: 1' in headers
    assert fallback == png


def test_first_offline_upgrade_keeps_old_image(setup):
    env, data = session(setup)
    old_cache = data / 'cache/pages/overview.png'
    old_cache.parent.mkdir(parents=True, exist_ok=True)
    Image.new('L', (600, 800), 128).save(old_cache)
    env['HTTP_X_DASHBOARD_VIEWPORT'] = '584x706'
    assert call(env, 'cached=overview')[1] == old_cache.read_bytes()


@pytest.mark.parametrize('viewport', ['600', '0x700', '600x90000', '600x400x500', '600x-1', '600x$(id)'])
def test_rejects_invalid_viewport_before_network(setup, viewport):
    env, _ = session(setup)
    env['HTTP_X_DASHBOARD_VIEWPORT'] = viewport
    assert b'Invalid viewport' in call(env, 'fetch=overview')[1]
    assert setup[3] == []
