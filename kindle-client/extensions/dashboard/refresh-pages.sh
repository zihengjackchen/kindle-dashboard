#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
acquire_lock || exit 1
check_enabled && power_preflight || exit 1
read_device_info
valid_dimension "$WIDTH" && valid_dimension "$HEIGHT" || exit 1
network_prepare || exit 1
original_page=$PAGE
result=0
log 'Refresh All Pages: at most five requests; no retries'
for PAGE in overview weather markets-1 markets-2 nas; do
    check_enabled || { result=1; break; }
    # Stop the batch at its first failure, retaining every existing page.
    if ! download_image; then result=1; break; fi
    mv -f "$TMP_IMAGE" "$CACHE_DIR/pages/$PAGE.png" || { result=1; break; }
    TMP_IMAGE=
    rm -f "$TMP_HEADERS"
    TMP_HEADERS=
done
PAGE=$original_page
if [ "$MOCK_MODE" != 1 ]; then sleep "$KUAL_SETTLE_SECONDS"; fi
show_cached_page || result=1
power_finish
exit "$result"
