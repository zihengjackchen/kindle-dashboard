#!/bin/sh
# shellcheck disable=SC2034
# REFRESH_DISPLAYED is consumed by start.sh.
# shellcheck source=common.sh
. "$DASHBOARD_DIR/lib/common.sh"
init_client || exit 1
# shellcheck source=device-info.sh
. "$DASHBOARD_DIR/lib/device-info.sh"
# shellcheck source=download.sh
. "$DASHBOARD_DIR/lib/download.sh"
# shellcheck source=display.sh
. "$DASHBOARD_DIR/lib/display.sh"
# shellcheck source=power.sh
. "$DASHBOARD_DIR/lib/power.sh"
# shellcheck source=session.sh
. "$DASHBOARD_DIR/lib/session.sh"
# shellcheck source=pages.sh
. "$DASHBOARD_DIR/lib/pages.sh"
# shellcheck source=telemetry.sh
. "$DASHBOARD_DIR/lib/telemetry.sh"

refresh_dashboard() {
    REFRESH_DISPLAYED=0
    check_enabled || return 1
    power_preflight || return 1
    read_device_info
    log "Device=$MODEL battery=${BATTERY:-unknown} charging=${CHARGING:-unknown} dimensions=${WIDTH:-unknown}x${HEIGHT:-unknown}"
    if ! valid_dimension "$WIDTH" || ! valid_dimension "$HEIGHT"; then
        fail 'Screen size unknown/out of range (320..2560); run diagnostics and set SCREEN_WIDTH/SCREEN_HEIGHT.'
        return 1
    fi
    display_backend || return 1
    # Bounded settle, never a repeating loop.
    if [ "$MOCK_MODE" != 1 ]; then sleep "$KUAL_SETTLE_SECONDS"; fi
    if network_prepare && download_image && commit_and_display; then
        cache_displayed_page || log 'ERROR could not retain page in carousel cache'
        REFRESH_DISPLAYED=1
        power_finish
        return 0
    fi
    if ! disabled && validate_png "$CACHE_DIR/dashboard.png"; then
        if display_image "$CACHE_DIR/dashboard.png"; then
            REFRESH_DISPLAYED=1
            log 'Retained and displayed previous cache; generated timestamp is stale'
        else log 'ERROR previous cache display failed'; fi
    fi
    power_finish
    return 1
}
