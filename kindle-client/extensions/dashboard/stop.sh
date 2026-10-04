#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
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
