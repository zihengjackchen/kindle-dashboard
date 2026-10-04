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
