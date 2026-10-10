#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
# shellcheck source=lib/common.sh
. "$DASHBOARD_DIR/lib/common.sh"
init_client || exit 1
# shellcheck source=lib/display.sh
. "$DASHBOARD_DIR/lib/display.sh"
# shellcheck source=lib/device-info.sh
. "$DASHBOARD_DIR/lib/device-info.sh"
. "$DASHBOARD_DIR/lib/httpd.sh"
acquire_lock || exit 1
TMP_REPORT=$(mktemp "$LOG_DIR/diagnostics.tmp.XXXXXX") || exit 1
diagnostic_report() {
    printf 'Kindle Dashboard diagnostics (read-only)\n'
    date -u
    uname -a
    uname -m
    cat /proc/cpuinfo 2>/dev/null
    cat /etc/pretty_version 2>/dev/null
    cat /etc/os-release 2>/dev/null
    free 2>/dev/null
    df -h
    for cmd in eips fbink curl wget lipc-get-prop lipc-set-prop gasgauge-info timeout fbset pngcheck powerd lipc-probe lipc-wait-event mkfifo sqlite3 mesquite busybox cksum; do
        printf '\n--- which %s ---\n' "$cmd"
        which "$cmd" 2>/dev/null || command -v "$cmd" || :
    done
    display_diagnostics
    if [ "$MOCK_MODE" != 1 ]; then
        printf '\n--- Battery class attributes ---\n'
        for supply in /sys/class/power_supply/*; do
            [ -d "$supply" ] || continue
            for attr in type capacity status online present; do
                [ -r "$supply/$attr" ] || continue
                printf '%s: ' "$supply/$attr"; head -c 256 "$supply/$attr"; printf '\n'
            done
        done
        printf '\n--- Candidate /sys/devices battery paths (bounded, names only) ---\n'
        probe find /sys/devices -maxdepth 8 -type f \( -name capacity -o -name battery_capacity -o -name charging -o -name status \) | head -n 100
        printf '\n--- Read-only power capabilities ---\n'
        cat /sys/power/state 2>/dev/null
        for prop in battLevel isCharging state flIntensity isUsbConnected preventScreenSaver; do
            printf 'powerd.%s: ' "$prop"; probe lipc-get-prop com.lab126.powerd "$prop"; printf '\n'
        done
        printf 'cmd.wirelessEnable: '; probe lipc-get-prop com.lab126.cmd wirelessEnable
        if command -v lipc-probe >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
            probe lipc-probe -a com.lab126.powerd | head -n 160
        fi
        printf '\n--- App capabilities ---\n'
        probe lipc-get-prop com.lab126.appmgrd activeApp
        select_httpd || :
        cat "$LOG_DIR/httpd-probe.txt"
        for light in /sys/class/backlight/*/brightness; do
            [ -r "$light" ] || continue
            printf '%s: ' "$light"; head -c 64 "$light"; printf '\n'
        done
        printf '\n--- Framebuffer metadata ---\n'
        for attr in name modes virtual_size bits_per_pixel rotate; do
            printf '%s: ' "$attr"; head -c 512 "/sys/class/graphics/fb0/$attr" 2>/dev/null; printf '\n'
        done
        probe fbset -s
    fi
    read_device_info
    printf '\n--- Normalized detection ---\n'
    printf 'battery=%s\ncharging=%s\nwidth=%s\nheight=%s\nmodel=%s\nfirmware=%s\nfbink=%s\neips=%s\n' \
        "${BATTERY:-unknown}" "${CHARGING:-unknown}" "${WIDTH:-unknown}" "${HEIGHT:-unknown}" "$MODEL" "$FIRMWARE" "$HAS_FBINK" "$HAS_EIPS"
    printf '\nNo Wi-Fi, power, framework, or lockscreen settings were changed.\n'
}
diagnostic_report 2>&1 | head -c 65536 > "$TMP_REPORT"
mv -f "$TMP_REPORT" "$LOG_DIR/diagnostics.txt" || exit 1
TMP_REPORT=
log 'Diagnostics saved to logs/diagnostics.txt'
printf 'Report: %s/diagnostics.txt\n' "$LOG_DIR"
