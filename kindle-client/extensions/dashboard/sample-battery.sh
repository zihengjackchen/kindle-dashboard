#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
acquire_lock || exit 1
read_device_info
battery_sample manual
log "Manual battery observation: battery=${BATTERY:-unknown} charging=${CHARGING:-unknown}"
