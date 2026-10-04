#!/bin/sh
# shellcheck disable=SC2034
# START_PENDING is read by the shared cleanup trap.
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
acquire_lock || exit 1
check_enabled || exit 1
power_preflight || exit 1
stop_listener
log 'Start Dashboard requested'
START_PENDING=1
printf 'started=%s\nmode=manual\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATE_DIR/active" || exit 1
refresh_result=0
refresh_dashboard || refresh_result=1
if [ "$REFRESH_DISPLAYED" != 1 ]; then
    rm -f "$STATE_DIR/active"
    log 'Start aborted: no image displayed; active marker removed'
else
    if ! start_listener; then
        log 'Wake restore unavailable; manual session remains usable'
        refresh_result=1
    fi
    log 'Dashboard active; native sleep remains unchanged'
fi
START_PENDING=0
exit "$refresh_result"
