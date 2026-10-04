import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile
import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name+'.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_setup_builds_matching_private_package_and_keeps_public_package_clean(tmp_path):
    shutil.copytree(ROOT / 'scripts', tmp_path / 'scripts', ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    shutil.copytree(ROOT / 'kindle-client', tmp_path / 'kindle-client', ignore=shutil.ignore_patterns('cache', 'logs', 'state'))
    (tmp_path / 'server').mkdir()
    shutil.copy(ROOT / 'server/.env.example', tmp_path / 'server/.env.example')
    command = [sys.executable, str(tmp_path/'scripts/setup.py'), '--nas-url', 'http://192.0.2.10:8080', '--device-id', 'bedside']
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    env = (tmp_path/'server/.env').read_text()
    token = next(line.split('=',1)[1].strip("'") for line in env.splitlines() if line.startswith('API_TOKEN='))
    assert len(token) == 48 and token not in result.stdout
    with ZipFile(tmp_path/'dist/private/kindle-dashboard-configured.zip') as archive:
        private = archive.read('extensions/dashboard/config.local.sh').decode()
        assert token in private and 'http://192.0.2.10:8080/dashboard.png' in private
        assert archive.testzip() is None
    # Even an installed private override in the source tree must be omitted.
    (tmp_path/'kindle-client/extensions/dashboard/config.local.sh').write_text(private)
    subprocess.run([sys.executable, str(tmp_path/'scripts/package-client.py')], check=True, capture_output=True)
    with ZipFile(tmp_path/'dist/kindle-dashboard-client.zip') as archive:
        assert not any(n.endswith('config.local.sh') for n in archive.namelist())
        assert not any(token.encode() in archive.read(n) for n in archive.namelist())
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert (tmp_path/'server/.env').read_text() == env


def test_battery_report_requires_uninterrupted_discharge():
    report = module('battery-report')
    rows = [{'epoch':'100000', 'battery':'80', 'charging':'0'}, {'epoch':'128800', 'battery':'78', 'charging':'0'}]
    assert report.summarize(rows)['percentage_points_per_hour'] == .25
    rows[1]['charging'] = '1'
    with pytest.raises(ValueError): report.summarize(rows)
    rows[1].update(charging='0', battery='81')
    with pytest.raises(ValueError): report.summarize(rows)


def test_truenas_export_filters_private_fields_and_keeps_fault_health(monkeypatch):
    exporter = module('export-truenas')
    monkeypatch.setattr(exporter, 'cpu_sample', lambda: (100, 50))
    monkeypatch.setattr(exporter.time, 'sleep', lambda _: None)
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **k: 'MemTotal: 100 kB\nMemAvailable: 25 kB\n' if str(path).replace('\\','/') == '/proc/meminfo' else original(path,*a,**k))
    responses = {'system.info': {'version':'TrueNAS-25.10', 'uptime':'1 day', 'system_serial':'PRIVATE'},
                 'pool.query': [{'name':'tank','status':'FAULTED','allocated':None,'size':None}],
                 'alert.list': [{'dismissed':False,'text':'PRIVATE'}]}
    result = exporter.export('tank', responses.__getitem__)
    assert result['pool_health'] == 'FAULTED' and result['used_percent'] is None
    assert result['alerts'] == 1 and result['memory_percent'] == 75
    assert 'PRIVATE' not in str(result)
