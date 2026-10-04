#!/bin/sh
# All page names come from this fixed allowlist; never use server-supplied paths.
cache_displayed_page() {
    TMP_IMAGE=$(mktemp "$CACHE_DIR/dashboard.tmp.XXXXXX") || return 1
    cp "$CACHE_DIR/dashboard.png" "$TMP_IMAGE" || return 1
    mv -f "$TMP_IMAGE" "$CACHE_DIR/pages/$PAGE.png" || return 1
    TMP_IMAGE=
}

show_cached_page() {
    check_enabled || return 1
    read_device_info
    valid_dimension "$WIDTH" && valid_dimension "$HEIGHT" || return 1
    display_backend || return 1
    validate_png "$CACHE_DIR/pages/$PAGE.png" || { fail 'Page not cached at this resolution; run Refresh All Pages first.'; return 1; }
    TMP_IMAGE=$(mktemp "$CACHE_DIR/dashboard.tmp.XXXXXX") || return 1
    cp "$CACHE_DIR/pages/$PAGE.png" "$TMP_IMAGE" || return 1
    commit_and_display
}

next_page() {
    case "$PAGE:$1" in
        overview:next|markets-1:previous) PAGE=weather ;;
        weather:next|markets-2:previous) PAGE=markets-1 ;;
        markets-1:next|nas:previous) PAGE=markets-2 ;;
        markets-2:next|overview:previous) PAGE=nas ;;
        nas:next|weather:previous) PAGE=overview ;;
        *) return 1 ;;
    esac
}
