#!/bin/sh
display_backend() {
    BACKEND=
    case "$DISPLAY_BACKEND" in
        auto)
            if command -v "$FBINK_BIN" >/dev/null 2>&1; then BACKEND=fbink
            elif command -v "$EIPS_BIN" >/dev/null 2>&1; then BACKEND=eips; fi ;;
        fbink|eips) BACKEND=$DISPLAY_BACKEND ;;
        *) fail 'DISPLAY_BACKEND must be auto, fbink or eips'; return 1 ;;
    esac
    if [ "$MOCK_MODE" = 1 ]; then BACKEND=${BACKEND:-fbink}; fi
    case "$BACKEND" in
        fbink) DISPLAY_BIN=$FBINK_BIN ;;
        eips) DISPLAY_BIN=$EIPS_BIN ;;
        *) fail 'No FBInk or eips found; configure a compatible installed backend.'; return 1 ;;
    esac
    if [ "$MOCK_MODE" != 1 ] && ! command -v "$DISPLAY_BIN" >/dev/null 2>&1; then
        fail "Display backend unavailable: $BACKEND"; return 1
    fi
    log "Display backend=$BACKEND mock=$MOCK_MODE"
}

display_run() {
    if [ "$MOCK_MODE" = 1 ]; then log "MOCK display command: $*"; return 0; fi
    # Diagnostics captures detailed backend help; do not grow the log with raw output.
    "$@" >/dev/null 2>&1
}

display_image() {
    display_allowed || { log 'Drawing suppressed: disabled, sleeping, locked or unverified'; return 1; }
    case "$BACKEND" in
        fbink) display_run "$DISPLAY_BIN" -q -f -c -g "file=$1" ;;
        eips) display_run "$DISPLAY_BIN" -f -g "$1" ;;
        *) return 1 ;;
    esac
}

clear_display() {
    display_allowed || return 1
    case "$BACKEND" in
        fbink) display_run "$DISPLAY_BIN" -q -f -k ;;
        eips) display_run "$DISPLAY_BIN" -c ;;
        *) return 1 ;;
    esac
}

full_refresh() {
    display_allowed || return 1
    case "$BACKEND" in
        fbink) display_run "$DISPLAY_BIN" -q -f -s ;;
        # Re-draw the entire cached image: eips refresh-only syntax varies.
        eips) [ -s "$CACHE_DIR/dashboard.png" ] && display_image "$CACHE_DIR/dashboard.png" ;;
        *) return 1 ;;
    esac
}

display_geometry() {
    detected_geometry=
    if command -v "$FBINK_BIN" >/dev/null 2>&1; then
        detected_geometry=$(probe "$FBINK_BIN" -e | tr ';' '\n' | awk -F= '
            {gsub(/[[:space:]]/, "", $1); gsub(/[^0-9]/, "", $2)}
            $1 == "screen_width" {w=$2} $1 == "screen_height" {h=$2}
            END {if (w && h) print w, h}')
    fi
    if [ -z "$detected_geometry" ] && command -v "$EIPS_BIN" >/dev/null 2>&1; then
        detected_geometry=$(probe "$EIPS_BIN" -i | awk '
            /(^|[[:space:]])xres[[:space:]:=]/ {s=$0; sub(/.*xres[[:space:]:=]+/, "", s); sub(/[^0-9].*/, "", s); w=s}
            /(^|[[:space:]])yres[[:space:]:=]/ {s=$0; sub(/.*yres[[:space:]:=]+/, "", s); sub(/[^0-9].*/, "", s); h=s}
            END {if (w && h) print w, h}')
    fi
    printf '%s\n' "$detected_geometry"
}

display_diagnostics() {
    if [ "$MOCK_MODE" = 1 ]; then printf 'MOCK: framebuffer probes skipped\n'; return; fi
    if command -v "$FBINK_BIN" >/dev/null 2>&1; then
        printf '\n--- FBInk help and geometry ---\n'
        probe "$FBINK_BIN" --help
        probe "$FBINK_BIN" -e
    fi
    if command -v "$EIPS_BIN" >/dev/null 2>&1; then
        printf '\n--- eips information (read-only -i) ---\n'
        probe "$EIPS_BIN" -i
    fi
}
