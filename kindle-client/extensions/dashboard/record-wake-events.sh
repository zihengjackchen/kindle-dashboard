#!/bin/sh
# Run from an existing terminal, then use the normal power button and unlock.
# Read-only and bounded to 90 seconds. No wake is requested by this script.
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/common.sh
. "$DASHBOARD_DIR/lib/common.sh"
init_client || exit 1
command -v timeout >/dev/null 2>&1 && command -v "$LIPC_WAIT_BIN" >/dev/null 2>&1 || exit 1
acquire_lock || exit 1
TMP_REPORT=$(mktemp "$LOG_DIR/events.tmp.XXXXXX") || exit 1
printf 'Recording power events for 90 seconds. Sleep, wake, then dismiss the native lockscreen normally.\n'
timeout 90 "$LIPC_WAIT_BIN" -m com.lab126.powerd '*' 2>/dev/null |
    while IFS= read -r event_line; do
        printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$event_line"
        printf 'powerd.state='; probe lipc-get-prop com.lab126.powerd state; printf '\n'
        if [ -n "$WAKE_UNLOCK_SOURCE" ] && [ -n "$WAKE_UNLOCK_PROPERTY" ]; then
            printf 'configured guard='; probe lipc-get-prop "$WAKE_UNLOCK_SOURCE" "$WAKE_UNLOCK_PROPERTY"; printf '\n'
        fi
    done | head -c 65536 > "$TMP_REPORT"
mv -f "$TMP_REPORT" "$LOG_DIR/wake-events.txt" || exit 1
TMP_REPORT=
log 'Saved read-only event trace to logs/wake-events.txt'
