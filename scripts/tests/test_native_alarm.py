"""Exercise the actual shell guards. These tests do not prove a hardware wake."""
import subprocess

import pytest

from test_client import SH, EXT, setup, nas  # noqa: F401


PRELUDE = r'''
. "$DASHBOARD_DIR/lib/client.sh"
. "$DASHBOARD_DIR/lib/native-alarm.sh"
NATIVE_ALARM_EXPERIMENT=1
NATIVE_ALARM_MODEL=test-model
NATIVE_ALARM_FIRMWARE=test-firmware
NATIVE_ALARM_KERNEL=test-kernel
LIPC_WAIT_BIN=true
fake_path=$(CDPATH='' cd "$DASHBOARD_DATA_DIR/bin" && pwd)
PATH="$fake_path:$PATH"
battery=75
usb=0
phase=active
hold=0
uname() { printf test-kernel; }
read_device_info() { MODEL=test-model; FIRMWARE=test-firmware; BATTERY=$battery; }
external_power() { printf '%s' "$usb"; }
probe() {
    if [ "$1" = lipc-get-prop ]; then
        case "$3" in state) printf '%s' "$phase" ;; preventScreenSaver) printf '%s' "$hold" ;; esac
    else printf '%s\n' "$*" >> "$STATE_DIR/writes"; fi
}
'''


def shell(setup, body):
    env, data, *_ = setup
    fake_bin = data / "bin"
    fake_bin.mkdir(exist_ok=True)
    for name in ("lipc-get-prop", "lipc-set-prop"):
        command = fake_bin / name
        command.write_text("#!/bin/sh\nexit 0\n", encoding="ascii", newline="\n")
        command.chmod(0o755)
    return subprocess.run([SH, "-c", PRELUDE + body], env=env, capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize("change", [
    "NATIVE_ALARM_EXPERIMENT=0", "NATIVE_ALARM_MODEL=other",
    "NATIVE_ALARM_FIRMWARE=other", "NATIVE_ALARM_KERNEL=other",
    "NATIVE_ALARM_MODEL=", "battery=19", "battery=", "usb=1", "usb=",
    "phase=screenSaver", "hold=1", 'touch "$DISABLE_FILE"',
    'touch "$STATE_DIR/app.pid"', 'touch "$STATE_DIR/active"',
])
def test_profile_refuses_unsafe_or_unverified_conditions(setup, change):
    result = shell(setup, change + '\n! native_alarm_profile || exit 11\n[ ! -f "$STATE_DIR/writes" ]\n')
    assert result.returncode == 0, result.stderr


def test_exact_profile_check_is_read_only(setup):
    result = shell(setup, 'native_alarm_profile || exit 11\n[ ! -f "$STATE_DIR/writes" ]\n')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("change,delay", [
    ("phase=active", "120"), ("phase=suspended", "120"),
    ("phase=screenSaver", "120"), ("NATIVE_ALARM_EXPERIMENT=0", "120"),
    ('touch "$DISABLE_FILE"', "120"), ("", "0"), ("", "59"),
    ("", "3601"), ("", "abc"), ("", "99999999999999999999"),
])
def test_alarm_write_is_blocked_outside_ready_window_or_limits(setup, change, delay):
    result = shell(setup, f'''phase=readyToSuspend
{change}
! native_alarm_arm {delay} || exit 11
[ ! -f "$STATE_DIR/writes" ]
''')
    assert result.returncode == 0, result.stderr


def test_only_native_relative_alarm_is_written(setup):
    result = shell(setup, '''phase=readyToSuspend
native_alarm_arm 120 || exit 11
[ "$(cat "$STATE_DIR/writes")" = 'lipc-set-prop -i com.lab126.powerd rtcWakeup 120' ]
''')
    assert result.returncode == 0, result.stderr


def test_native_alarm_rejection_is_not_reported_as_success(setup):
    result = shell(setup, '''phase=readyToSuspend
probe() {
    if [ "$1" = lipc-get-prop ]; then printf readyToSuspend; else return 1; fi
}
! native_alarm_arm 120
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("resume_event", ["wakeupFromSuspend 110", "resuming"])
def test_one_cycle_event_driver_arms_once_and_cleans_up(setup, resume_event):
    env, data, *_ = setup
    ext = data / "experiment"
    (ext / "lib").mkdir(parents=True)
    for name in ("state", "logs", "bin"):
        (ext / name).mkdir()
    for name in ("test-native-sleep.sh", "lib/native-alarm.sh", "lib/common.sh"):
        (ext / name).write_bytes((EXT / name).read_bytes())
    for name in ("lipc-get-prop", "lipc-set-prop"):
        path = ext / "bin" / name
        path.write_text("#!/bin/sh\nexit 0\n", encoding="ascii", newline="\n")
        path.chmod(0o755)
    (ext / "lib/client.sh").write_text(r'''
. "$DASHBOARD_DIR/lib/common.sh"
STATE_DIR=$DASHBOARD_DIR/state
LOG_DIR=$DASHBOARD_DIR/logs
LOG_FILE=$LOG_DIR/dashboard.log
MAX_LOG_BYTES=65536
DISABLE_FILE=$DASHBOARD_DIR/disabled
PATH="$DASHBOARD_DIR/bin:$PATH"
NATIVE_ALARM_EXPERIMENT=1
NATIVE_ALARM_MODEL=test-model
NATIVE_ALARM_FIRMWARE=test-firmware
NATIVE_ALARM_KERNEL=$(uname -r)
LIPC_WAIT_BIN=$DASHBOARD_DIR/events.sh
read_device_info() { MODEL=test-model; FIRMWARE=test-firmware; BATTERY=75; }
external_power() { printf 0; }
probe() {
    if [ "$1" = lipc-get-prop ]; then
        case "$3" in
            state) cat "$STATE_DIR/phase" ;;
            preventScreenSaver) printf 0 ;;
        esac
    elif [ "$1" = lipc-set-prop ]; then
        printf '%s\n' "$*" >> "$STATE_DIR/writes"
        if [ "$4" = powerButton ]; then
            printf readyToSuspend > "$STATE_DIR/phase"
            touch "$STATE_DIR/go"
        fi
    fi
}
export DASHBOARD_DIR
''', encoding="ascii", newline="\n")
    events = ext / "events.sh"
    events.write_text('''#!/bin/sh
while [ ! -f "$DASHBOARD_DIR/state/go" ]; do sleep 0.05; done
printf 'readyToSuspend 10\nreadyToSuspend 10\nRESUME_EVENT\n'
'''.replace("RESUME_EVENT", resume_event), encoding="ascii", newline="\n")
    events.chmod(0o755)
    (ext / "state/phase").write_text("active", encoding="ascii")
    result = subprocess.run([SH, (ext / "test-native-sleep.sh").as_posix(), "--run"],
                            env=env, capture_output=True, text=True, timeout=20)
    report = (ext / "logs/native-sleep-test.txt").read_text() if (ext / "logs/native-sleep-test.txt").exists() else ""
    assert result.returncode == 0, result.stderr + report
    assert (ext / "state/writes").read_text().splitlines() == [
        "lipc-set-prop -i com.lab126.powerd powerButton 1",
        "lipc-set-prop -i com.lab126.powerd rtcWakeup 120",
    ]
    assert "RESULT: resume observed" in report
    assert not (ext / "state/native-sleep-test.lock").exists()
