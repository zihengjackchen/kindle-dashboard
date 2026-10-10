import subprocess
from pathlib import Path
from test_client import SH, EXT, nas, setup  # noqa: F401


def test_power_and_light_are_scoped_and_restored(setup):
    env,data,*_=setup
    # Shell functions fake only LIPC. Run the actual power ownership logic.
    body='''
    . "$DASHBOARD_DIR/lib/client.sh"
    . "$DASHBOARD_DIR/lib/app-power.sh"
    MOCK_MODE=0
    KEEP_AWAKE_PLUGGED=1
    light=8
    inhibited=0
    usb=1
    app=org.kindledashboard.app
    phase=active
    probe() {
        if [ "$1" = lipc-get-prop ]; then
            case "$3" in flIntensity) echo "$light" ;; preventScreenSaver) echo "$inhibited" ;; isUsbConnected) echo "$usb" ;; activeApp) echo "$app" ;; state) echo "$phase" ;; esac
        else
            case "$3" in flIntensity) light=$4 ;; preventScreenSaver) inhibited=$4 ;; esac
        fi
    }
    frontlight_off
    [ "$light" = 0 ] || exit 11
    frontlight_off
    [ "$(cat "$STATE_DIR/prior-light")" = 8 ] || exit 12
    app_power_update
    [ "$inhibited" = 1 ] || exit 13
    usb=0
    app_power_update
    [ "$inhibited" = 0 ] || exit 14
    usb=1
    app_power_update
    phase=screenSaver
    app_power_update
    [ "$inhibited" = 0 ] || exit 15
    phase=active
    app=other.app
    app_power_update
    [ "$inhibited" = 0 ] || exit 16
    app=org.kindledashboard.app
    usb=
    app_power_update
    [ "$inhibited" = 0 ] || exit 19
    VERIFIED_EXTERNAL_POWER_PATH=/sys/class/power_supply/test/present
    present=1
    read_first() {
        if [ "$1" = "$VERIFIED_EXTERNAL_POWER_PATH" ]; then echo "$present";
        else [ ! -r "$1" ] || head -n 1 "$1"; fi
    }
    app_power_update
    [ "$inhibited" = 1 ] || exit 20
    present=0
    app_power_update
    [ "$inhibited" = 0 ] || exit 21
    present=1; inhibited=1
    app_power_update
    [ ! -f "$STATE_DIR/prior-inhibit" ] || exit 22
    app_power_release
    [ "$inhibited" = 1 ] || exit 23
    app_light_restore
    [ "$light" = 8 ] || exit 17
    [ ! -f "$STATE_DIR/prior-light" ] || exit 18
    '''
    result=subprocess.run([SH,'-c',body],env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
