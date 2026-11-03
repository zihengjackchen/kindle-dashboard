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
    app_foreground || return 0
    light=$(probe lipc-get-prop com.lab126.powerd flIntensity)
    if ! is_uint "$light" || [ "$light" -gt 24 ]; then log 'Frontlight interface unavailable'; return 1; fi
    [ -f "$STATE_DIR/prior-light" ] || printf '%s\n' "$light" > "$STATE_DIR/prior-light"
    if [ -n "$VERIFIED_FRONTLIGHT_PATH" ]; then
        raw=$(frontlight_raw_read "$VERIFIED_FRONTLIGHT_PATH") || { log 'ERROR verified frontlight path unreadable'; return 1; }
        is_uint "$raw" || return 1
        if [ ! -f "$STATE_DIR/prior-light-raw" ]; then
            printf '%s\n' "$raw" > "$STATE_DIR/prior-light-raw"
            printf '%s\n' "$VERIFIED_FRONTLIGHT_PATH" > "$STATE_DIR/prior-light-path"
        fi
        # Native powerd can relight LEDs after resume. Native events call this
        # again, but an already-dark light needs no write or polling loop.
        [ "$light" != 0 ] || [ "$raw" != 0 ] || return 0
    fi
    probe lipc-set-prop com.lab126.powerd flIntensity 0 || return 1
    if [ -n "$VERIFIED_FRONTLIGHT_PATH" ]; then
        frontlight_raw_write "$VERIFIED_FRONTLIGHT_PATH" 0 || { log 'ERROR frontlight hardware-off failed'; return 1; }
        log 'Frontlight hardware brightness verified zero'
    else
        log 'Frontlight at native minimum; hardware-off path is not configured'
    fi
}

frontlight_raw_read() {
    case "$1" in /sys/class/backlight/*/brightness) read_first "$1" ;; *) return 1 ;; esac
}

frontlight_raw_write() {
    case "$1" in /sys/class/backlight/*/brightness) ;; *) return 1 ;; esac
    is_uint "$2" || return 1
    printf '%s\n' "$2" > "$1" || return 1
    [ "$(frontlight_raw_read "$1")" = "$2" ] || return 1
    # Where available, verify the driver's actual output as well as its target.
    actual=${1%/brightness}/actual_brightness
    [ ! -r "$actual" ] || [ "$(read_first "$actual")" = "$2" ]
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
            if [ -f "$STATE_DIR/prior-light-raw" ]; then
                raw=$(read_first "$STATE_DIR/prior-light-raw")
                light_path=$(read_first "$STATE_DIR/prior-light-path")
                [ -n "$light_path" ] || light_path=$VERIFIED_FRONTLIGHT_PATH
                frontlight_raw_write "$light_path" "$raw" || { log 'ERROR frontlight restore failed; recovery state retained'; return 1; }
            fi
            rm -f "$STATE_DIR/prior-light" "$STATE_DIR/prior-light-raw" "$STATE_DIR/prior-light-path"
            log 'Prior frontlight brightness restored'
        fi
    fi
}

app_power_update() {
    if ! app_foreground; then app_power_release; return; fi
    frontlight_off || :
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
