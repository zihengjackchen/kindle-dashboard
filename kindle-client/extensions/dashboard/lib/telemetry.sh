#!/bin/sh
# Read only; no sampling daemon, radio changes, or extra network requests.
read_rssi() {
    if [ "$MOCK_MODE" = 1 ]; then signal=$MOCK_RSSI
    else signal=$(awk 'NR > 2 && /:/ {sub(/\.$/, "", $4); print $4; exit}' /proc/net/wireless 2>/dev/null); fi
    case "$signal" in -[0-9]*) ;; *) return 1 ;; esac
    magnitude=${signal#-}
    is_uint "$magnitude" && [ "$magnitude" -ge 1 ] && [ "$magnitude" -le 127 ] || return 1
    printf '%s' "$signal"
}

append_telemetry() {
    [ "$SEND_TELEMETRY" = 1 ] || return 0
    REQUEST_URL="$REQUEST_URL&device_id=$(safe_label "$DEVICE_ID")"
    rssi=$(read_rssi) || rssi=
    [ -z "$rssi" ] || REQUEST_URL="$REQUEST_URL&rssi=$rssi"
    REQUEST_URL="$REQUEST_URL&firmware=$(safe_label "$FIRMWARE")"
    external=$(external_power)
    case "$external" in 0|1) REQUEST_URL="$REQUEST_URL&external_power=$external" ;; esac
    inhibit=$(probe lipc-get-prop com.lab126.powerd preventScreenSaver)
    case "$inhibit" in 0|1) REQUEST_URL="$REQUEST_URL&sleep_inhibited=$inhibit" ;; esac
    if [ "$KEEP_AWAKE_PLUGGED" = 1 ]; then policy=plugged-in; else policy=native-sleep; fi
    REQUEST_URL="$REQUEST_URL&power_policy=$policy"
    up=$(cut -d. -f1 /proc/uptime 2>/dev/null)
    is_uint "$up" && REQUEST_URL="$REQUEST_URL&uptime_seconds=$up"
    free_mib=$(df -k "$DASHBOARD_DIR" 2>/dev/null | awk 'NR==2 {print int($4/1024)}')
    is_uint "$free_mib" && REQUEST_URL="$REQUEST_URL&storage_free_mib=$free_mib"
    light=$(probe lipc-get-prop com.lab126.powerd flIntensity)
    if is_uint "$light" && [ "$light" -le 100 ]; then REQUEST_URL="$REQUEST_URL&frontlight=$light"; fi
    for field in fetch_seconds fetch_failures last_success_epoch; do
        value=$(read_first "$STATE_DIR/$field")
        # Epoch values require more digits than ordinary config integers.
        case "$value" in ''|*[!0-9]*) continue ;; esac
        [ "${#value}" -le 10 ] || continue
        REQUEST_URL="$REQUEST_URL&$field=$value"
    done
}

record_fetch() {
    fetch_end=$(date +%s)
    elapsed=$((fetch_end - FETCH_STARTED))
    [ "$elapsed" -ge 0 ] && [ "$elapsed" -le 86400 ] || elapsed=0
    failures=$(read_first "$STATE_DIR/fetch_failures")
    is_uint "$failures" || failures=0
    if [ "$1" = ok ]; then failures=0; else
        [ "$failures" -ge 999999 ] || failures=$((failures + 1))
    fi
    for field in fetch_seconds fetch_failures last_success_epoch; do
        case "$field" in
            fetch_seconds) value=$elapsed ;;
            fetch_failures) value=$failures ;;
            last_success_epoch) [ "$1" = ok ] || continue; value=$fetch_end ;;
        esac
        printf '%s\n' "$value" > "$STATE_DIR/$field.tmp" && mv -f "$STATE_DIR/$field.tmp" "$STATE_DIR/$field"
    done
    log "Fetch result=$1 seconds=$elapsed consecutive_failures=$failures"
}

battery_sample() {
    samples=$LOG_DIR/battery.csv
    if [ -f "$samples" ] && [ "$(wc -c < "$samples")" -ge "$MAX_LOG_BYTES" ]; then mv -f "$samples" "$samples.1"; fi
    [ -f "$samples" ] || printf 'epoch,battery,charging,rssi,reason\n' > "$samples"
    printf '%s,%s,%s,%s,%s\n' "$(date +%s)" "${BATTERY:-}" "${CHARGING:-}" "$(read_rssi)" "$1" >> "$samples"
}
