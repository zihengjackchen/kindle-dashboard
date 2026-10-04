#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
restore_session=${1:-} restore_ticket=${2:-}
restore_authorized() {
    [ -n "$restore_session" ] && [ -n "$restore_ticket" ] && [ -f "$STATE_DIR/active" ] &&
        [ "$(read_first "$STATE_DIR/session-token")" = "$restore_session" ] &&
        [ "$(read_first "$STATE_DIR/wake-ticket")" = "$restore_ticket" ] &&
        [ "$(read_first "$STATE_DIR/native-phase")" = restoring ] && ! disabled && native_unlocked
}
restore_authorized || exit 1
sleep "$WAKE_SETTLE_SECONDS"
restore_authorized || exit 1
acquire_lock || exit 1
read_device_info
wake_profile_valid || exit 1
valid_dimension "$WIDTH" && valid_dimension "$HEIGHT" || exit 1
display_backend || exit 1
validate_png "$CACHE_DIR/dashboard.png" || { fail 'Wake restore has no valid cached image'; exit 1; }
restore_authorized || exit 1
display_image "$CACHE_DIR/dashboard.png" || exit 1
# Never overwrite a newer sleep transition with an old worker's completion.
if restore_authorized; then printf '%s\n' active > "$STATE_DIR/native-phase"; fi
log 'Wake restore: cached image displayed; no network request'
