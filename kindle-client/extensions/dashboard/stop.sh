#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
. "$DASHBOARD_DIR/lib/app-power.sh"
# Revoke bridge access immediately, even while a download is in progress.
rm -f "$STATE_DIR/app-key"
app_power_release
app_light_restore
if [ -f "$STATE_DIR/app.pid" ]; then
    app_pid=$(read_first "$STATE_DIR/app.pid")
    if is_uint "$app_pid" && [ -r "/proc/$app_pid/cmdline" ] && tr '\000' '\n' < "/proc/$app_pid/cmdline" | grep -F -x "$DASHBOARD_DIR/app-session.sh" >/dev/null; then
        kill -TERM "$app_pid" 2>/dev/null || :
        # POSIX sh may defer TERM until its current sleep finishes. Wait for
        # cleanup so an immediate reopen cannot reuse a revoked session.
        stop_wait=0
        while [ -r "/proc/$app_pid/cmdline" ] && tr '\000' '\n' < "/proc/$app_pid/cmdline" | grep -F -x "$DASHBOARD_DIR/app-session.sh" >/dev/null; do
            [ "$stop_wait" -lt 12 ] || { fail 'App is still stopping; retry shortly'; exit 1; }
            sleep 1
            stop_wait=$((stop_wait + 1))
        done
    else
        rm -f "$STATE_DIR/app.pid" "$STATE_DIR/app-heartbeat"
        rmdir "$STATE_DIR/app.lock" 2>/dev/null || :
    fi
    probe lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home >/dev/null || :
fi
probe lipc-set-prop com.lab126.appmgrd stop app://org.kindledashboard.app >/dev/null || :
# Stop always works with the kill switch present or automation flags misconfigured.
rm -f "$STATE_DIR/active"
stop_listener
acquire_lock || exit 1
log 'Stop Dashboard requested'
rm -f "$STATE_DIR/active"
# Under our lock, these can only be leftovers from an interrupted prior action.
for stale in "$CACHE_DIR"/dashboard.tmp.* "$CACHE_DIR"/headers.tmp.* "$CACHE_DIR"/previous.tmp.*; do
    [ ! -f "$stale" ] || rm -f "$stale"
done
restore_interface
power_finish
log 'Dashboard stopped; cache retained'
