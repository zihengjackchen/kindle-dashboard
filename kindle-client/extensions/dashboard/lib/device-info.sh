#!/bin/sh
# shellcheck disable=SC2034
battery_percent() {
    bp=$(printf '%s' "$1" | tr -d '[:space:]%')
    if is_uint "$bp" && [ "$bp" -le 100 ]; then printf '%s' "$bp"; return 0; fi
    return 1
}

charging_value() {
    case "$1" in
        1|Charging|charging) printf 1 ;;
        0|Discharging|discharging|Full|full|'Not charging') printf 0 ;;
        *) return 1 ;;
    esac
}

external_power() {
    external=$(probe lipc-get-prop com.lab126.powerd isUsbConnected)
    case "$external" in 0|1) printf '%s' "$external"; return ;; esac
    # This firmware exposes the cable flag in battStateInfo, not isUsbConnected.
    # Match only the named JSON boolean; never treat battery/online as USB power.
    external=$(probe lipc-get-prop com.lab126.powerd battStateInfo | tr -d '[:space:]')
    case "$external" in
        *'"usb":true'*) printf 1; return ;;
        *'"usb":false'*) printf 0; return ;;
    esac
    case "$VERIFIED_EXTERNAL_POWER_PATH" in
        /sys/class/power_supply/*/present|/sys/class/power_supply/*/online)
            external=$(read_first "$VERIFIED_EXTERNAL_POWER_PATH")
            case "$external" in 0|1) printf '%s' "$external"; return ;; esac ;;
    esac
    return 1
}

read_device_info() {
    BATTERY='' CHARGING='' WIDTH=$SCREEN_WIDTH HEIGHT=$SCREEN_HEIGHT
    MODEL=$DEVICE_MODEL FIRMWARE=unknown
    HAS_FBINK=0 HAS_EIPS=0
    command -v "$FBINK_BIN" >/dev/null 2>&1 && HAS_FBINK=1
    command -v "$EIPS_BIN" >/dev/null 2>&1 && HAS_EIPS=1
    if [ "$MOCK_MODE" = 1 ]; then
        BATTERY=$(battery_percent "$MOCK_BATTERY")
        CHARGING=$(charging_value "$MOCK_CHARGING")
        WIDTH=$MOCK_WIDTH HEIGHT=$MOCK_HEIGHT MODEL=mock-paperwhite FIRMWARE=mock
        return 0
    fi
    if [ -n "$BATTERY_CAPACITY_FILE" ]; then BATTERY=$(battery_percent "$(read_first "$BATTERY_CAPACITY_FILE")"); fi
    if [ -n "$BATTERY_STATUS_FILE" ]; then CHARGING=$(charging_value "$(read_first "$BATTERY_STATUS_FILE")"); fi
    if command -v lipc-get-prop >/dev/null 2>&1; then
        [ -n "$BATTERY" ] || BATTERY=$(battery_percent "$(probe lipc-get-prop com.lab126.powerd battLevel)")
        [ -n "$CHARGING" ] || CHARGING=$(charging_value "$(probe lipc-get-prop com.lab126.powerd isCharging)")
    fi
    # Class entries may be symlinks. Only read capacity/status from batteries.
    for supply in /sys/class/power_supply/* /sys/devices/platform/*/power_supply/*; do
        [ -d "$supply" ] || continue
        supply_type=$(read_first "$supply/type")
        case "$supply_type:$supply" in
            Battery:*|*:*/batt*|*:*/BAT*)
                [ -n "$BATTERY" ] || BATTERY=$(battery_percent "$(read_first "$supply/capacity")")
                [ -n "$CHARGING" ] || CHARGING=$(charging_value "$(read_first "$supply/status")") ;;
        esac
    done
    if [ -z "$BATTERY" ] && command -v gasgauge-info >/dev/null 2>&1; then
        BATTERY=$(battery_percent "$(probe gasgauge-info -c)")
    fi
    # Legacy Kindle battery drivers; both paths are optional, read-only fallbacks.
    for legacy in /sys/devices/platform/pmic_battery.1/power_supply/mc13892_bat/capacity /sys/devices/platform/pmic_battery.1/battery_capacity; do
        [ -n "$BATTERY" ] || BATTERY=$(battery_percent "$(read_first "$legacy")")
    done
    geometry=
    if [ -z "$WIDTH" ] || [ -z "$HEIGHT" ]; then geometry=$(display_geometry); fi
    if [ -n "$geometry" ]; then
        [ -n "$WIDTH" ] || WIDTH=$(printf '%s\n' "$geometry" | awk '{print $1}')
        [ -n "$HEIGHT" ] || HEIGHT=$(printf '%s\n' "$geometry" | awk '{print $2}')
    fi
    if { [ -z "$WIDTH" ] || [ -z "$HEIGHT" ]; } && command -v fbset >/dev/null 2>&1; then
        geometry=$(probe fbset -s | awk '$1 == "geometry" {print $2, $3; exit}')
        [ -n "$WIDTH" ] || WIDTH=$(printf '%s\n' "$geometry" | awk '{print $1}')
        [ -n "$HEIGHT" ] || HEIGHT=$(printf '%s\n' "$geometry" | awk '{print $2}')
    fi
    # virtual_size may include double-buffering; do NOT infer physical size from it.
    if [ -z "$MODEL" ] && [ -r /proc/device-tree/model ]; then MODEL=$(tr -d '\000' < /proc/device-tree/model); fi
    if [ -z "$MODEL" ]; then MODEL=$(awk -F: '/^Hardware/ {sub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null); fi
    MODEL=$(safe_label "${MODEL:-unknown}")
    if [ -r /etc/pretty_version ]; then FIRMWARE=$(read_first /etc/pretty_version)
    elif [ -r /etc/os-release ]; then FIRMWARE=$(awk -F= '$1 == "PRETTY_NAME" {print $2; exit}' /etc/os-release)
    elif [ -r /etc/version.txt ]; then FIRMWARE=$(head -n 1 /etc/version.txt | sed 's/^System Software Version: //'); fi
    return 0
}
