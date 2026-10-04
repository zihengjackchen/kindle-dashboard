#!/bin/sh
# shellcheck disable=SC2034
# CACHE_PENDING and temporary paths are consumed by common.sh cleanup.
validate_png() {
    [ -s "$1" ] || return 1
    png_size=$(wc -c < "$1")
    [ "$png_size" -le "$MAX_IMAGE_BYTES" ] || return 1
    od -An -v -tu1 "$1" | awk -v width="$WIDTH" -v height="$HEIGHT" \
        -v filesize="$png_size" -v maxbytes="$MAX_IMAGE_BYTES" \
        -f "$DASHBOARD_DIR/lib/validate-png.awk" || return 1
    if command -v pngcheck >/dev/null 2>&1; then pngcheck -q "$1" >/dev/null 2>&1 || return 1; fi
}

build_url() {
    # Labels are restricted ASCII, so no external URL encoder is needed.
    case "$DASHBOARD_URL" in http://*|https://*) ;; *) fail 'DASHBOARD_URL must use HTTP(S)'; return 1 ;; esac
    case "$DASHBOARD_URL" in *\?*|*\#*|*@*|*' '* ) fail 'Use a plain endpoint URL without credentials, query or fragment'; return 1 ;; esac
    REQUEST_URL="$DASHBOARD_URL?width=$WIDTH&height=$HEIGHT&device=$(safe_label "$MODEL")&page=$PAGE"
    [ -z "$BATTERY" ] || REQUEST_URL="$REQUEST_URL&battery=$BATTERY"
    [ -z "$CHARGING" ] || REQUEST_URL="$REQUEST_URL&charging=$CHARGING"
    append_telemetry
    log "Request $REQUEST_URL auth=$([ -n "$API_TOKEN" ] && printf bearer || printf none)"
}

http_fetch() (
    # A subshell scopes the file-size limit to the downloader. POSIX ulimit -f
    # uses 512-byte blocks (some shells use 1024); final byte validation is exact.
    if ! ulimit -f "$(( (MAX_IMAGE_BYTES + 511) / 512 ))" 2>/dev/null; then
        # Git Bash has no RLIMIT_FSIZE; only the explicit host mock may proceed.
        [ "$MOCK_MODE" = 1 ] || exit 1
    fi
    clean_token=$(printf '%s' "$API_TOKEN" | tr -d '\015\012')
    [ "$clean_token" = "$API_TOKEN" ] || exit 1
    client=$HTTP_CLIENT
    if [ "$client" = auto ]; then
        if command -v curl >/dev/null 2>&1; then client=curl; else client=wget; fi
    fi
    case "$client" in
        curl)
            command -v curl >/dev/null 2>&1 || exit 1
            set -- --silent --fail --connect-timeout "$CONNECT_TIMEOUT_SECONDS" \
                --max-time "$DOWNLOAD_TIMEOUT_SECONDS" --max-filesize "$MAX_IMAGE_BYTES" \
                --dump-header "$TMP_HEADERS" --output "$TMP_IMAGE" --write-out '%{http_code}'
            [ -z "$API_TOKEN" ] || set -- "$@" --header "Authorization: Bearer $API_TOKEN"
            # No redirects: do not forward authentication or accept a login page.
            status=$(curl -q "$@" "$REQUEST_URL" 2>/dev/null) || exit 1
            [ "$status" = 200 ] || exit 1
            ;;
        wget)
            command -v wget >/dev/null 2>&1 || exit 1
            # wget -T alone is not a total deadline. Fail closed without timeout.
            command -v timeout >/dev/null 2>&1 || exit 1
            # Older BusyBox wget follows redirects and may forward the bearer
            # token. Require redirect control before sending any request.
            wget --help 2>&1 | grep -q -- '--max-redirect' || exit 1
            set -- -S -T "$CONNECT_TIMEOUT_SECONDS" -O "$TMP_IMAGE" --tries=1 --max-redirect=0
            if [ -n "$API_TOKEN" ]; then
                wget --help 2>&1 | grep -q -- '--header' || exit 1
                set -- "$@" --header="Authorization: Bearer $API_TOKEN"
            fi
            timeout "$DOWNLOAD_TIMEOUT_SECONDS" wget "$@" "$REQUEST_URL" > /dev/null 2> "$TMP_HEADERS" || exit 1
            # Reject every non-200 status.
            awk '$1 ~ /^HTTP\// {seen=1; if ($2 != "200") bad=1} END {exit (!seen || bad)}' "$TMP_HEADERS" || exit 1
            ;;
        *) exit 1 ;;
    esac
    awk 'tolower($1) == "content-type:" {v=tolower($2); gsub(/\r/, "", v); sub(/;.*/, "", v); if (v == "image/png") ok=1} END {exit !ok}' "$TMP_HEADERS" || exit 1
    # A legacy server may silently ignore page queries. Require acknowledgement.
    awk -v page="$PAGE" 'tolower($1) == "x-dashboard-page:" {v=$2; gsub(/\r/, "", v); if (v == page) ok=1} END {exit !ok}' "$TMP_HEADERS"
)

download_image() {
    build_url || return 1
    FETCH_STARTED=$(date +%s)
    battery_sample fetch
    TMP_IMAGE=$(mktemp "$CACHE_DIR/dashboard.tmp.XXXXXX") || return 1
    TMP_HEADERS=$(mktemp "$CACHE_DIR/headers.tmp.XXXXXX") || return 1
    if ! http_fetch; then record_fetch failed; fail 'Download failed (HTTP/auth/network/deadline/client capability); cache retained'; return 1; fi
    log 'Download succeeded; HTTP 200 and image/png'
    if ! validate_png "$TMP_IMAGE"; then record_fetch failed; fail 'PNG validation failed; cache retained'; return 1; fi
    record_fetch ok
    log "PNG validation passed dimensions=${WIDTH}x${HEIGHT}"
}

commit_and_display() {
    # Backup is temporary and same-filesystem. Even backend decode failure must
    # not permanently replace the last working cache.
    had_cache=0
    if [ -f "$CACHE_DIR/dashboard.png" ]; then
        TMP_BACKUP=$(mktemp "$CACHE_DIR/previous.tmp.XXXXXX") || return 1
        cp "$CACHE_DIR/dashboard.png" "$TMP_BACKUP" || return 1
        had_cache=1
    fi
    check_enabled || return 1
    CACHE_PENDING=1
    mv -f "$TMP_IMAGE" "$CACHE_DIR/dashboard.png" || { CACHE_PENDING=0; return 1; }
    TMP_IMAGE=
    if display_image "$CACHE_DIR/dashboard.png"; then
        CACHE_PENDING=0
        printf '%s\n' "$PAGE" > "$STATE_DIR/current-page"
        log 'Cache committed and full-screen image displayed'
        return 0
    fi
    log 'ERROR display failed; rolling back cache'
    if [ "$had_cache" = 1 ]; then
        mv -f "$TMP_BACKUP" "$CACHE_DIR/dashboard.png" || return 1
        TMP_BACKUP=
    else
        rm -f "$CACHE_DIR/dashboard.png"
    fi
    CACHE_PENDING=0
    return 1
}
