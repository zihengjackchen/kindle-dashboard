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
    [ -z "$HTTP_PID" ] || kill "$HTTP_PID" 2>/dev/null || :
    # Discard the native WebKit instance: its in-memory session key is now stale.
    probe lipc-set-prop com.lab126.appmgrd stop app://org.kindledashboard.app >/dev/null || :
    rm -f "$STATE_DIR/app.pid" "$STATE_DIR/app-key" "$STATE_DIR/app-heartbeat" "$STATE_DIR/active"
    rm -f "$STATE_DIR/web/$APP_KEY/index.html" "$STATE_DIR/web/$APP_KEY/app.js" "$STATE_DIR/web/$APP_KEY/session.js"
    rmdir "$STATE_DIR/web/$APP_KEY" 2>/dev/null || :
    rmdir "$STATE_DIR/app.lock" 2>/dev/null || :
    log 'App closed; bridge stopped; prior light and power restored'
}
HTTP_PID=
trap app_cleanup 0
trap 'exit 0' TERM INT HUP
printf '%s\n' "$$" > "$STATE_DIR/app.pid"
date +%s > "$STATE_DIR/app-heartbeat"
printf 'mode=app\n' > "$STATE_DIR/active"
export DASHBOARD_DIR
"$HTTPD_BIN" httpd -f -p "127.0.0.1:$APP_PORT" -h "$STATE_DIR/web" &
HTTP_PID=$!
frontlight_off || :
was_foreground=0
was_sleeping=0
while [ "$(read_first "$STATE_DIR/app-key")" = "$APP_KEY" ] && ! disabled; do
    kill -0 "$HTTP_PID" 2>/dev/null || exit 1
    phase=$(probe lipc-get-prop com.lab126.powerd state)
    case "$phase" in screenSaver|suspended|readyToSuspend)
        app_power_release
        was_sleeping=1
        sleep 10
        continue ;;
    esac
    if [ "$was_sleeping" = 1 ]; then
        date +%s > "$STATE_DIR/app-heartbeat"
        was_sleeping=0
    fi
    last=$(read_first "$STATE_DIR/app-heartbeat")
    is_uint "$last" || case "$last" in ''|*[!0-9]*) break ;; esac
    [ "$(($(date +%s)-last))" -le 90 ] || break
    if app_foreground; then
        was_foreground=1
        app_power_update
    else
        app_power_release
        # Once observed, closing/switching apps ends our session even if WebKit
        # keeps running and fails to deliver a lifecycle callback.
        current_app=$(probe lipc-get-prop com.lab126.appmgrd activeApp)
        if [ "$was_foreground" = 1 ] && [ -n "$current_app" ]; then
            case "$current_app" in org.kindledashboard.app|app://org.kindledashboard.app) ;; *) break ;; esac
        fi
    fi
    sleep 10
done
