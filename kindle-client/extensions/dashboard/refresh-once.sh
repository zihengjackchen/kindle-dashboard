#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
acquire_lock || exit 1
log 'Manual refresh requested'
refresh_dashboard
