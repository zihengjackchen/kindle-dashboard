#!/bin/sh
# Loopback-only CGI. No arbitrary command/path/URL inputs and no CORS grant.
: "${DASHBOARD_DIR:=/mnt/us/extensions/dashboard}"
# shellcheck source=../lib/client.sh
. "$DASHBOARD_DIR/lib/client.sh"
# shellcheck source=../lib/app-power.sh
. "$DASHBOARD_DIR/lib/app-power.sh"
# shellcheck source=../lib/bundle.sh
. "$DASHBOARD_DIR/lib/bundle.sh"
respond() { printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n%s\n' "$1"; }
if [ "$REQUEST_METHOD" != POST ] || [ -z "$HTTP_X_DASHBOARD_SESSION" ] || [ "$HTTP_X_DASHBOARD_SESSION" != "$(read_first "$STATE_DIR/app-key")" ] || disabled; then
    printf 'Status: 403 Forbidden\r\n'; respond '{"error":"Session closed"}'; exit 0
fi
# App viewport images must not replace full-panel framebuffer page caches.
LEGACY_PAGE_CACHE=$CACHE_DIR/pages
CACHE_DIR=$CACHE_DIR/app
mkdir -p "$CACHE_DIR/pages" || exit 1
case "$QUERY_STRING" in
    bundle|cached-bundle|commit-bundle=*)
        bundle_action ;;
    heartbeat)
        date +%s > "$STATE_DIR/app-heartbeat"
        respond '{"ok":true}' ;;
    enter)
        date +%s > "$STATE_DIR/app-heartbeat"
        log 'Dashboard UI connected to local bridge'
        frontlight_off >/dev/null 2>&1 || :
        respond '{"ok":true}' ;;
    close)
        rm -f "$STATE_DIR/app-key"
        app_power_release; app_light_restore
        respond '{"ok":true}'
        probe lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home >/dev/null || : ;;
    settings)
        settings_url=${DASHBOARD_URL%/dashboard.png}/client-config.json
        tmp=$(mktemp "$STATE_DIR/settings.XXXXXX") || exit 1
        if curl -q -fsS --connect-timeout "$CONNECT_TIMEOUT_SECONDS" --max-time "$DOWNLOAD_TIMEOUT_SECONDS" --max-filesize 16384 --header "Authorization: Bearer $API_TOKEN" "$settings_url" > "$tmp" 2>/dev/null && [ "$(wc -c < "$tmp")" -le 16384 ]; then
            printf 'Content-Type: application/json\r\nCache-Control: no-store\r\n\r\n'; cat "$tmp"
        else respond '{"error":"Settings unavailable"}'; fi
        rm -f "$tmp" ;;
    commit=*)
        pair=${QUERY_STRING#commit=}; PAGE=${pair%%:*}; revision=${pair#*:}
        valid_page "$PAGE" || { respond '{"error":"Invalid commit"}'; exit 0; }
        case "$revision" in ''|*[!0-9]*) respond '{"error":"Invalid revision"}'; exit 0 ;; esac
        [ "${#revision}" -le 10 ] || exit 0
        acquire_lock >/dev/null 2>&1 || { respond '{"error":"Refresh busy"}'; exit 0; }
        pending=$CACHE_DIR/pages/$PAGE.pending
        actual=$(cksum "$pending" 2>/dev/null | awk '{print $1}')
        if [ "$actual" = "$revision" ]; then
            mv -f "$pending" "$CACHE_DIR/pages/$PAGE.png" || { respond '{"error":"Cache commit failed"}'; exit 0; }
            printf '%s\n' "$PAGE" > "$STATE_DIR/current-page"
            respond '{"ok":true}'
        else respond '{"error":"Image superseded"}'; fi ;;
    cached=*|fetch=*)
        verb=${QUERY_STRING%%=*}; PAGE=${QUERY_STRING#*=}
        valid_page "$PAGE" || { respond '{"error":"Invalid page"}'; exit 0; }
        if [ "$MOCK_MODE" != 1 ] && [ "$verb" = fetch ] && ! app_foreground; then
            respond '{"error":"Refresh paused until Dashboard is foreground and Kindle unlocked"}'; exit 0
        fi
        read_device_info
        if [ -n "$HTTP_X_DASHBOARD_VIEWPORT" ]; then
            case "$HTTP_X_DASHBOARD_VIEWPORT" in *x*) ;; *) respond '{"error":"Invalid viewport"}'; exit 0 ;; esac
            viewport_width=${HTTP_X_DASHBOARD_VIEWPORT%x*}
            viewport_height=${HTTP_X_DASHBOARD_VIEWPORT#*x}
            if ! valid_dimension "$viewport_width" || ! valid_dimension "$viewport_height"; then
                respond '{"error":"Invalid viewport"}'; exit 0
            fi
            WIDTH=$viewport_width HEIGHT=$viewport_height
        fi
        if ! valid_dimension "$WIDTH" || ! valid_dimension "$HEIGHT"; then respond '{"error":"Screen size unknown"}'; exit 0; fi
        printf 'X-Dashboard-Battery: %s\r\nX-Dashboard-Charging: %s\r\n' "$BATTERY" "$CHARGING"
        serve=$CACHE_DIR/pages/$PAGE.png
        # Retain the pre-upgrade image during an offline first launch.
        [ -f "$serve" ] || serve=$LEGACY_PAGE_CACHE/$PAGE.png
        if [ "$verb" = fetch ]; then
            acquire_lock >/dev/null 2>&1 || { respond '{"error":"Refresh busy"}'; exit 0; }
            if network_prepare && download_image; then
                if disabled || [ "$HTTP_X_DASHBOARD_SESSION" != "$(read_first "$STATE_DIR/app-key")" ]; then respond '{"error":"Session ended"}'; exit 0; fi
                # Commit only after the app has decoded this exact image.
                serve=$CACHE_DIR/pages/$PAGE.pending
                mv -f "$TMP_IMAGE" "$serve" || { respond '{"error":"Cache write failed"}'; exit 0; }; TMP_IMAGE=
                revision=$(cksum "$serve" | awk '{print $1}')
                printf 'X-Dashboard-Revision: %s\r\n' "$revision"
            else
                printf 'X-Dashboard-Stale: 1\r\n'
            fi
        fi
        if validate_cached_png "$serve"; then
            printf 'Content-Type: image/png\r\nCache-Control: no-store\r\n\r\n'
            cat "$serve"
        else respond '{"error":"No cached image; check Wi-Fi and NAS"}'; fi ;;
    *) respond '{"error":"Unknown action"}' ;;
esac
