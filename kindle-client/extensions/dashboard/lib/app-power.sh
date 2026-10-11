#!/bin/sh
# Native power/light properties only. No RTC, raw suspend, lockscreen or framework changes.
app_foreground() {
    [ "$MOCK_MODE" = 1 ] && return 0
    app_name=$(probe lipc-get-prop com.lab126.appmgrd activeApp) || return 1
    case "$app_name" in org.kindledashboard.app|app://org.kindledashboard.app) ;; *) return 1 ;; esac
    [ "$(probe lipc-get-prop com.lab126.powerd state)" = active ]
}

frontlight_off() {
    [ "$APP_FRONTLIGHT_OFF" = 1 ] || return 0
    if [ "$MOCK_MODE" = 1 ]; then log 'MOCK frontlight off'; return 0; fi
    light=$(probe lipc-get-prop com.lab126.powerd flIntensity)
    if ! is_uint "$light" || [ "$light" -gt 24 ]; then log 'Frontlight interface unavailable'; return 1; fi
    [ -f "$STATE_DIR/prior-light" ] || printf '%s\n' "$light" > "$STATE_DIR/prior-light"
    # PW2/PW3 LIPC level 0 is a faint light. Use only a user-verified path.
    if [ -n "$VERIFIED_FRONTLIGHT_PATH" ] && [ -w "$VERIFIED_FRONTLIGHT_PATH" ]; then
        case "$VERIFIED_FRONTLIGHT_PATH" in /sys/class/backlight/*/brightness)
            [ -f "$STATE_DIR/prior-light-raw" ] || cat "$VERIFIED_FRONTLIGHT_PATH" > "$STATE_DIR/prior-light-raw"
            ;;
        esac
    fi
    probe lipc-set-prop com.lab126.powerd flIntensity 0 || return 1
    if [ -n "$VERIFIED_FRONTLIGHT_PATH" ] && [ -f "$STATE_DIR/prior-light-raw" ]; then
        case "$VERIFIED_FRONTLIGHT_PATH" in /sys/class/backlight/*/brightness) printf '0\n' > "$VERIFIED_FRONTLIGHT_PATH" ;; esac
    fi
    log 'Frontlight set to minimum; true off requires hardware confirmation on older Paperwhites'
}

app_power_release() {
    if [ -f "$STATE_DIR/prior-inhibit" ]; then
        previous=$(read_first "$STATE_DIR/prior-inhibit")
        case "$previous" in 0|1)
            if probe lipc-set-prop com.lab126.powerd preventScreenSaver "$previous"; then rm -f "$STATE_DIR/prior-inhibit"; fi ;;
        esac
    fi
}

app_light_restore() {
    if [ -f "$STATE_DIR/prior-light" ]; then
        previous=$(read_first "$STATE_DIR/prior-light")
        if is_uint "$previous" && [ "$previous" -le 24 ] && probe lipc-set-prop com.lab126.powerd flIntensity "$previous"; then
            if [ -f "$STATE_DIR/prior-light-raw" ] && [ -n "$VERIFIED_FRONTLIGHT_PATH" ]; then
                raw=$(read_first "$STATE_DIR/prior-light-raw")
                case "$VERIFIED_FRONTLIGHT_PATH" in /sys/class/backlight/*/brightness) is_uint "$raw" && printf '%s\n' "$raw" > "$VERIFIED_FRONTLIGHT_PATH" ;; esac
            fi
            rm -f "$STATE_DIR/prior-light" "$STATE_DIR/prior-light-raw"
        fi
    fi
}

app_power_update() {
    if ! app_foreground; then app_power_release; return; fi
    # Charging may be false when full: read external supply, not battery charging.
    if [ "$KEEP_AWAKE_ON_BATTERY" != 1 ]; then
        [ "$KEEP_AWAKE_PLUGGED" = 1 ] || { app_power_release; return; }
        external=$(external_power)
        [ "$external" = 1 ] || { app_power_release; return; }
    fi
    inhibit=$(probe lipc-get-prop com.lab126.powerd preventScreenSaver)
    case "$inhibit" in 0|1) ;; *) log 'Keep-awake property unavailable; using native sleep'; return ;; esac
    # Do not claim an inhibitor already held by another app (e.g. KOSSH).
    # Reevaluate on later native events if that app releases it.
    [ "$inhibit" = 0 ] || return 0
    if [ ! -f "$STATE_DIR/prior-inhibit" ]; then
        printf '%s\n' "$inhibit" > "$STATE_DIR/prior-inhibit"
    fi
    # Another app can release the shared native property during our session.
    # Reassert our requested hold on a native event even if we already own it.
    if probe lipc-set-prop com.lab126.powerd preventScreenSaver 1; then
        log "Foreground app requested stay-awake battery_enabled=$KEEP_AWAKE_ON_BATTERY; native power button remains available"
    else
        app_power_release
        log 'ERROR could not request foreground stay-awake'
    fi
}
