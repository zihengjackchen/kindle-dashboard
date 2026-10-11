#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$DASHBOARD_DIR/lib/client.sh"
. "$DASHBOARD_DIR/lib/app-power.sh"
. "$DASHBOARD_DIR/lib/httpd.sh"
select_httpd || exit 1
[ "$1" = "$(read_first "$STATE_DIR/app-key")" ] || exit 1
APP_KEY=$1
mkdir "$STATE_DIR/app.lock" 2>/dev/null || exit 1
app_cleanup() {
    app_power_release
    app_light_restore
    for child in "$HTTP_PID" "$EVENT_PID" "$CHECK_PID" "$BUTTON_PID"; do
        [ -z "$child" ] || kill "$child" 2>/dev/null || :
    done
    probe lipc-set-prop com.lab126.appmgrd stop app://org.kindledashboard.app >/dev/null || :
    rm -f "$STATE_DIR/app.pid" "$STATE_DIR/app-key" "$STATE_DIR/app-heartbeat" "$STATE_DIR/active"
    rm -f "$STATE_DIR/web/$APP_KEY/index.html" "$STATE_DIR/web/$APP_KEY/app.js" "$STATE_DIR/web/$APP_KEY/session.js"
    rmdir "$STATE_DIR/web/$APP_KEY" 2>/dev/null || :
    if [ -n "$RUNTIME" ]; then rm -f "$RUNTIME/events"; rmdir "$RUNTIME" 2>/dev/null || :; fi
    rmdir "$STATE_DIR/app.lock" 2>/dev/null || :
    log 'App closed; bridge and native event listener stopped; prior light and power restored'
}
HTTP_PID='' EVENT_PID='' CHECK_PID='' BUTTON_PID='' RUNTIME=''
trap app_cleanup 0
trap 'exit 0' TERM INT HUP
printf '%s\n' "$$" > "$STATE_DIR/app.pid"
date +%s > "$STATE_DIR/app-heartbeat"
printf 'mode=app\n' > "$STATE_DIR/active"
export DASHBOARD_DIR
"$HTTPD_BIN" httpd -f -p "127.0.0.1:$APP_PORT" -h "$STATE_DIR/web" &
HTTP_PID=$!
frontlight_off || :
# A FIFO lives in /tmp (USB storage is FAT). read sleeps until a native event,
# a startup deadline or the 30-minute audit; there is no browser heartbeat.
command -v "$LIPC_WAIT_BIN" >/dev/null 2>&1 || { fail 'Native event listener required'; exit 1; }
RUNTIME=$(mktemp -d /tmp/dashboard-app.XXXXXX) || exit 1
mkfifo "$RUNTIME/events" || exit 1
exec 3<> "$RUNTIME/events"
(
    event_child=
    trap '[ -z "$event_child" ] || kill "$event_child" 2>/dev/null; exit 0' TERM INT HUP
    "$LIPC_WAIT_BIN" -m -l '*' >&3 2>/dev/null <<'SOURCES' &
com.lab126.powerd
com.lab126.appmgrd
com.lab126.hal
SOURCES
    event_child=$!
    wait "$event_child"
    printf 'listener-ended\n' >&3
) &
EVENT_PID=$!
# This timer waits interruptibly: TERM cleanup never waits for a 30-minute sleep.
(
    timer_pid=
    trap '[ -z "$timer_pid" ] || kill "$timer_pid" 2>/dev/null; exit 0' TERM INT HUP
    sleep 30 & timer_pid=$!; wait "$timer_pid"
    printf 'startup-check\n' >&3
    while :; do
        sleep 1800 & timer_pid=$!; wait "$timer_pid"
        printf 'audit\n' >&3
    done
) &
CHECK_PID=$!
log 'Native event supervision active; fallback audit=1800s; browser heartbeat disabled'
was_foreground=0
manual_sleep=0
while IFS= read -r native_event <&3; do
    if [ "$(read_first "$STATE_DIR/app-key")" != "$APP_KEY" ] || disabled; then break; fi
    # -l prints the source before the event; ignore unrelated power telemetry.
    case "$native_event" in com.lab126.*\ *) native_event=${native_event#* } ;; esac
    event_name=${native_event%% *}
    case "$event_name" in
        listener-ended) log 'ERROR native event listener ended; restoring normal power policy'; break ;;
        powerButtonPressed)
            log 'Power button event: release app hold, then verify native sleep state'
            app_power_release; manual_sleep=1
            if [ -z "$BUTTON_PID" ] || ! kill -0 "$BUTTON_PID" 2>/dev/null; then
                # KOSSH also emits this event when stopping SSH without sleeping.
                # One delayed check distinguishes that case from native sleep.
                (
                    button_sleep=
                    trap '[ -z "$button_sleep" ] || kill "$button_sleep" 2>/dev/null; exit 0' TERM INT HUP
                    sleep 5 & button_sleep=$!; wait "$button_sleep"
                    printf 'power-button-check\n' >&3
                ) &
                BUTTON_PID=$!
            fi
            continue ;;
        power-button-check) BUTTON_PID=''; manual_sleep=0 ;;
        outOfScreenSaver|resuming) log "Native wake event=$event_name"; manual_sleep=0 ;;
        appStarted|appPaused|appStateChange|processExited|goingToScreenSaver|readyToSuspend|suspending|usbPlugIn|usbPlugOut|charging|notCharging|startup-check|audit) ;;
        *) continue ;;
    esac
    if ! kill -0 "$HTTP_PID" 2>/dev/null || ! kill -0 "$EVENT_PID" 2>/dev/null; then break; fi
    phase=$(probe lipc-get-prop com.lab126.powerd state)
    case "$phase" in screenSaver|suspended|readyToSuspend)
        log "Native sleep event=$event_name state=$phase; app hold released"
        app_power_release; continue ;;
    esac
    if app_foreground; then
        was_foreground=1
        [ "$manual_sleep" = 1 ] || app_power_update
    else
        app_power_release
        current_app=$(probe lipc-get-prop com.lab126.appmgrd activeApp)
        if [ "$was_foreground" = 1 ] && [ -n "$current_app" ]; then
            case "$current_app" in org.kindledashboard.app|app://org.kindledashboard.app) ;; *) log "Native foreground changed event=$event_name app=$current_app; closing dashboard session"; break ;; esac
        fi
        [ "$event_name" != startup-check ] || { log 'ERROR native UI did not reach foreground'; break; }
    fi
done
