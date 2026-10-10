#!/bin/sh
# One bounded JSON download contains settings and all PNGs. Mesquite decodes
# every image before acknowledging the exact pending file for atomic commit.
bundle_action() {
    case "$QUERY_STRING" in
        commit-bundle=*)
            revision=${QUERY_STRING#commit-bundle=}
            case "$revision" in ''|*[!0-9]*) respond '{"error":"Invalid revision"}'; return ;; esac
            [ "${#revision}" -le 10 ] || { respond '{"error":"Invalid revision"}'; return; }
            acquire_lock >/dev/null 2>&1 || { respond '{"error":"Refresh busy"}'; return; }
            actual=$(cksum "$CACHE_DIR/bundle.pending" 2>/dev/null | awk '{print $1}')
            if [ "$actual" != "$revision" ]; then respond '{"error":"Bundle superseded"}'; return; fi
            if mv -f "$CACHE_DIR/bundle.pending" "$CACHE_DIR/bundle.json"; then
                log 'All-page bundle decoded and atomically committed'
                respond '{"ok":true}'
            else respond '{"error":"Bundle cache commit failed"}'; fi
            return ;;
        bundle)
            if [ "$MOCK_MODE" != 1 ] && ! app_foreground; then
                respond '{"error":"Refresh paused until Dashboard is foreground and Kindle unlocked"}'; return
            fi
            read_device_info
            if [ -n "$HTTP_X_DASHBOARD_VIEWPORT" ]; then
                WIDTH=${HTTP_X_DASHBOARD_VIEWPORT%x*} HEIGHT=${HTTP_X_DASHBOARD_VIEWPORT#*x}
                case "$HTTP_X_DASHBOARD_VIEWPORT" in *x*) ;; *) WIDTH=invalid ;; esac
            fi
            if ! valid_dimension "$WIDTH" || ! valid_dimension "$HEIGHT"; then
                respond '{"error":"Invalid viewport"}'; return
            fi
            acquire_lock >/dev/null 2>&1 || { respond '{"error":"Refresh busy"}'; return; }
            # Keep existing telemetry/auth/deadline rules; change only endpoint/type.
            DASHBOARD_URL=${DASHBOARD_URL%/dashboard.png}/dashboard-bundle.json
            build_url || { respond '{"error":"Invalid server URL"}'; return; }
            FETCH_STARTED=$(date +%s)
            battery_sample fetch
            TMP_IMAGE=$(mktemp "$CACHE_DIR/bundle.tmp.XXXXXX") || return 1
            TMP_HEADERS=$(mktemp "$CACHE_DIR/headers.tmp.XXXXXX") || return 1
            MAX_IMAGE_BYTES=8388608
            if network_prepare && http_fetch application/json && [ -s "$TMP_IMAGE" ] && [ "$(wc -c < "$TMP_IMAGE")" -le "$MAX_IMAGE_BYTES" ]; then
                if disabled || [ "$HTTP_X_DASHBOARD_SESSION" != "$(read_first "$STATE_DIR/app-key")" ]; then
                    respond '{"error":"Session ended"}'; return
                fi
                mv -f "$TMP_IMAGE" "$CACHE_DIR/bundle.pending" || { respond '{"error":"Cache write failed"}'; return; }
                TMP_IMAGE=
                revision=$(cksum "$CACHE_DIR/bundle.pending" | awk '{print $1}')
                log 'Bundle downloaded; waiting for all PNGs to decode before commit'
                record_fetch ok
                printf 'X-Dashboard-Revision: %s\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n\r\n' "$revision"
                cat "$CACHE_DIR/bundle.pending"
                return
            fi
            record_fetch failed
            log 'ERROR bundle download failed; all cached pages retained'
            printf 'X-Dashboard-Stale: 1\r\n' ;;
    esac
    if [ -s "$CACHE_DIR/bundle.json" ]; then
        printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n'
        cat "$CACHE_DIR/bundle.json"
    else respond '{"error":"No cached bundle; check Wi-Fi and NAS"}'; fi
}
