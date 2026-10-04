#!/bin/sh
power_preflight() {
    if [ "$ENABLE_EXPERIMENTAL_POWER" != 0 ] || [ "$AUTO_REFRESH" != 0 ]; then
        fail 'Power automation is not implemented pending diagnostics; keep both feature flags at 0.'
        return 1
    fi
    return 0
}

network_prepare() {
    if [ "$MOCK_MODE" = 1 ]; then log 'MOCK network: using host connection'; return 0; fi
    # Read-only observation. Other firmware may not expose this property.
    if command -v lipc-get-prop >/dev/null 2>&1; then
        wireless=$(probe lipc-get-prop com.lab126.cmd wirelessEnable)
        if [ "$wireless" = 0 ]; then
            fail 'Wi-Fi is off. Enable/connect it in Kindle Settings, then refresh.'
            return 1
        fi
    fi
    log 'Network: using existing connection; Wi-Fi controls unchanged'
}

power_finish() {
    log 'Power: action exiting; no suspend request or inhibitor; normal Kindle power policy remains active'
}

restore_interface() {
    log 'Recovery: framework was never stopped; return to KUAL/Home normally'
    # KUAL Stop uses exitmenu=false + refresh=true to redraw its normal menu.
    # SSH users must reopen KUAL or navigate the normal UI to trigger repaint.
}
