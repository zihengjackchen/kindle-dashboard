#!/bin/sh
# shellcheck disable=SC2034
# wake_sequence is consumed by the sourced event state machine.
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
session_token=${1:-}
session_runtime=${2:-}
case "$session_token:$session_runtime" in kindle-dashboard.*:/tmp/kindle-dashboard.*) ;; *) exit 1 ;; esac
[ "$session_runtime" = "/tmp/$session_token" ] && [ -d "$session_runtime" ] || exit 1
event_pid='' restore_pid='' wake_sequence=0
terminate_child() {
    is_uint "$1" || return 0
    if [ "$(awk '/^PPid:/ {print $2}' "/proc/$1/status" 2>/dev/null)" = "$$" ]; then
        kill -TERM "$1" 2>/dev/null || :
    fi
}
listener_cleanup() {
    [ -z "$event_pid" ] || terminate_child "$event_pid"
    [ -z "$restore_pid" ] || terminate_child "$restore_pid"
    [ -z "$event_pid" ] || wait "$event_pid" 2>/dev/null || :
    [ -z "$restore_pid" ] || wait "$restore_pid" 2>/dev/null || :
    rm -f "$session_runtime/events"
    rmdir "$session_runtime" 2>/dev/null || :
    if [ "$(read_first "$STATE_DIR/session-token")" = "$session_token" ]; then
        rm -f "$STATE_DIR/listener.pid" "$STATE_DIR/session-token" "$STATE_DIR/wake-ticket"
        printf '%s\n' unknown > "$STATE_DIR/native-phase"
        log 'Wake listener ended; automatic drawing disabled until restart'
    fi
}
trap listener_cleanup 0
trap 'exit 0' TERM INT HUP
[ "$(read_first "$STATE_DIR/session-token")" = "$session_token" ] || exit 1
printf '%s\n' "$$" > "$STATE_DIR/listener.pid"
mkfifo "$session_runtime/events" || exit 1
"$LIPC_WAIT_BIN" -m com.lab126.powerd '*' > "$session_runtime/events" 2>/dev/null &
event_pid=$!
queue_restore() {
    # One worker at a time; a new sleep event invalidates its ticket immediately.
    if [ -n "$restore_pid" ]; then wait "$restore_pid" 2>/dev/null || :; fi
    sh "$DASHBOARD_DIR/restore-on-wake.sh" "$session_token" "$1" &
    restore_pid=$!
}
while IFS= read -r native_event; do
    if [ "$(read_first "$STATE_DIR/session-token")" != "$session_token" ] || [ ! -f "$STATE_DIR/active" ] || disabled; then break; fi
    # Accept only the two known untimestamped forms of lipc-wait-event output.
    case "$native_event" in com.lab126.powerd\ *) native_event=${native_event#com.lab126.powerd } ;; esac
    native_event=${native_event%% *}
    handle_native_event "$native_event"
done < "$session_runtime/events"
# EOF/failure is terminal, never a restart loop.
