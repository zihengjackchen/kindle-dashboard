#!/bin/sh
# shellcheck disable=SC2034
# Shared globals are used by other sourced libraries.
init_client() {
    umask 077
    PATH="$PATH:/usr/sbin:/sbin:/usr/bin:/bin"
    export PATH LC_ALL=C
    # shellcheck source=../config.sh
    . "$DASHBOARD_DIR/config.sh"
    # Optional private setup generated on your computer, excluded from Git.
    # shellcheck disable=SC1091
    [ ! -f "$DASHBOARD_DIR/config.local.sh" ] || . "$DASHBOARD_DIR/config.local.sh"
    DATA_DIR=$DASHBOARD_DIR
    if [ "$MOCK_MODE" = 1 ]; then DATA_DIR=${DASHBOARD_DATA_DIR:-$DASHBOARD_DIR}; fi
    CACHE_DIR=$DATA_DIR/cache
    STATE_DIR=$DATA_DIR/state
    LOG_DIR=$DATA_DIR/logs
    mkdir -p "$CACHE_DIR" "$CACHE_DIR/pages" "$STATE_DIR" "$LOG_DIR" || return 1
    LOG_FILE=$LOG_DIR/dashboard.log
    LOCK_DIR=$STATE_DIR/action.lock
    LOCK_OWNED=0
    TMP_IMAGE='' TMP_HEADERS='' TMP_BACKUP='' TMP_REPORT=''
    CACHE_PENDING=0
    START_PENDING=0
    PAGE=$(read_first "$STATE_DIR/current-page")
    PAGE=${PAGE:-$DEFAULT_PAGE}
    valid_page "$PAGE" || { printf 'Unknown dashboard page\n' >&2; return 1; }
    for config_number in "$CONNECT_TIMEOUT_SECONDS" "$DOWNLOAD_TIMEOUT_SECONDS" "$KUAL_SETTLE_SECONDS" "$WAKE_SETTLE_SECONDS" "$MAX_IMAGE_BYTES" "$MAX_LOG_BYTES"; do
        is_uint "$config_number" || { printf 'Invalid numeric configuration\n' >&2; return 1; }
    done
    [ "$CONNECT_TIMEOUT_SECONDS" -ge 1 ] && [ "$CONNECT_TIMEOUT_SECONDS" -le 60 ] &&
        [ "$DOWNLOAD_TIMEOUT_SECONDS" -ge 1 ] && [ "$DOWNLOAD_TIMEOUT_SECONDS" -le 120 ] &&
        [ "$KUAL_SETTLE_SECONDS" -le 10 ] &&
        [ "$WAKE_SETTLE_SECONDS" -le 5 ] &&
        [ "$MAX_IMAGE_BYTES" -ge 1024 ] && [ "$MAX_IMAGE_BYTES" -le 8388608 ] &&
        [ "$MAX_LOG_BYTES" -ge 1024 ] && [ "$MAX_LOG_BYTES" -le 1048576 ] || {
            printf 'Configuration limits invalid; see config.sh\n' >&2; return 1;
        }
}

log() {
    if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -ge "$MAX_LOG_BYTES" ]; then
        mv -f "$LOG_FILE" "$LOG_FILE.1"
    fi
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LOG_FILE"
}

fail() { log "ERROR $*"; printf '%s\n' "$*" >&2; return 1; }
is_uint() { case "$1" in ''|*[!0-9]*) return 1 ;; esac; [ "${#1}" -le 9 ]; }
valid_dimension() { is_uint "$1" && [ "$1" -ge 320 ] && [ "$1" -le 2560 ]; }
valid_page() { case "$1" in overview|weather|markets-1|markets-2|nas) return 0 ;; *) return 1 ;; esac; }
disabled() { [ -e "$DISABLE_FILE" ]; }
check_enabled() { if disabled; then fail "Recovery kill switch present: $DISABLE_FILE"; else return 0; fi; }

acquire_lock() {
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        fail 'Another action or stale lock exists; see docs/recovery.md.'
        return 1
    fi
    LOCK_OWNED=1
    printf '%s\n' "$$" > "$LOCK_DIR/pid"
    trap 'cleanup' 0
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
}

cleanup() {
    # Restore the previous cache if TERM/HUP/INT interrupts a pending draw.
    if [ "$CACHE_PENDING" = 1 ]; then
        if [ -n "$TMP_BACKUP" ] && [ -f "$TMP_BACKUP" ]; then
            if mv -f "$TMP_BACKUP" "$CACHE_DIR/dashboard.png"; then
                TMP_BACKUP=
                log 'Recovery: interrupted display transaction rolled back'
            else
                log "ERROR rollback rename failed; preserved backup: $TMP_BACKUP"
                TMP_BACKUP=
            fi
        else
            rm -f "$CACHE_DIR/dashboard.png"
            log 'Recovery: interrupted first display removed'
        fi
    fi
    if [ "$START_PENDING" = 1 ]; then
        rm -f "$STATE_DIR/active"
        log 'Recovery: interrupted start marker removed'
    fi
    for cleanup_file in "$TMP_IMAGE" "$TMP_HEADERS" "$TMP_BACKUP" "$TMP_REPORT"; do
        [ -z "$cleanup_file" ] || rm -f "$cleanup_file"
    done
    if [ "$LOCK_OWNED" = 1 ]; then
        rm -f "$LOCK_DIR/pid"
        rmdir "$LOCK_DIR" 2>/dev/null || :
    fi
}

# Never eval output returned by device commands.
probe() {
    if command -v timeout >/dev/null 2>&1; then timeout 5 "$@" 2>/dev/null
    else "$@" 2>/dev/null; fi
}

read_first() { [ -r "$1" ] && head -n 1 "$1" 2>/dev/null; }
safe_label() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_' | cut -c 1-80; }
