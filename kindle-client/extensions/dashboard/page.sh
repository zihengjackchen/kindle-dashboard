#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
acquire_lock || exit 1
next_page "${1:-next}" || exit 1
if [ "$MOCK_MODE" != 1 ]; then sleep "$KUAL_SETTLE_SECONDS"; fi
log "Offline page navigation: $PAGE"
show_cached_page
