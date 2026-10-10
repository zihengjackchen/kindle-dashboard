#!/bin/sh
# Never assume the stock BusyBox was built with the optional HTTP applet.
select_httpd() {
    HTTPD_BIN=
    if [ "$BUSYBOX_BIN" = auto ] || [ "$BUSYBOX_BIN" = busybox ]; then
        set -- "$DASHBOARD_DIR/bin/busybox" busybox /mnt/us/usbnet/bin/busybox
    else
        set -- "$BUSYBOX_BIN"
    fi
    : > "$LOG_DIR/httpd-probe.txt"
    for candidate in "$@"; do
        printf 'Candidate: %s\n' "$candidate" >> "$LOG_DIR/httpd-probe.txt"
        if ! command -v "$candidate" >/dev/null 2>&1; then
            printf 'Not installed\n' >> "$LOG_DIR/httpd-probe.txt"
            continue
        fi
        if command -v timeout >/dev/null 2>&1; then
            help=$(timeout 5 "$candidate" httpd --help 2>&1)
        else
            help=$("$candidate" httpd --help 2>&1)
        fi
        printf '%s\n' "$help" | head -c 4096 >> "$LOG_DIR/httpd-probe.txt"
        if printf '%s\n' "$help" | grep -q -- '-p' &&
           printf '%s\n' "$help" | grep -q -- '-h' &&
           printf '%s\n' "$help" | grep -q -- '-f'; then
            HTTPD_BIN=$candidate
            export HTTPD_BIN
            log "Local HTTP backend=$HTTPD_BIN"
            return 0
        fi
    done
    fail 'No compatible HTTP helper found; see logs/httpd-probe.txt and docs/kindle-app.md'
}
