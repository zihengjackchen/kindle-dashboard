#!/bin/sh
# A session owns only a blocking event subscriber, never a suspend inhibitor.
native_unlocked() {
    if [ "$MOCK_MODE" = 1 ]; then
        [ "$(read_first "$STATE_DIR/mock-lock")" = unlocked ]
    else
        [ -n "$WAKE_UNLOCK_SOURCE" ] && [ -n "$WAKE_UNLOCK_PROPERTY" ] && [ -n "$WAKE_UNLOCK_VALUE" ] || return 1
        guard=$(probe lipc-get-prop "$WAKE_UNLOCK_SOURCE" "$WAKE_UNLOCK_PROPERTY") || return 1
        [ "$guard" = "$WAKE_UNLOCK_VALUE" ]
    fi
}

display_allowed() {
    disabled && return 1
    case "$(read_first "$STATE_DIR/native-phase")" in sleeping|locked|unknown) return 1 ;; esac
    if [ "$WAKE_RESTORE" = 1 ]; then wake_profile_valid && native_unlocked || return 1; fi
    return 0
}

wake_profile_valid() {
    [ "$WAKE_RESTORE" = 1 ] || return 1
    if [ "$MOCK_MODE" = 1 ]; then return 0; fi
    if [ -z "$WAKE_VERIFIED_MODEL" ] || [ -z "$WAKE_VERIFIED_FIRMWARE" ]; then fail 'Wake profile needs verified model and firmware'; return 1; fi
    if [ "$MODEL" != "$WAKE_VERIFIED_MODEL" ] || [ "$FIRMWARE" != "$WAKE_VERIFIED_FIRMWARE" ]; then fail 'Wake profile does not match this model/firmware'; return 1; fi
    if [ -z "$WAKE_UNLOCK_SOURCE" ] || [ -z "$WAKE_UNLOCK_PROPERTY" ] || [ -z "$WAKE_UNLOCK_VALUE" ]; then fail 'Wake profile needs a read-only lockscreen-exit guard'; return 1; fi
    if ! command -v "$LIPC_WAIT_BIN" >/dev/null 2>&1 || ! command -v timeout >/dev/null 2>&1; then
        fail 'Wake listener needs lipc-wait-event and timeout'; return 1
    fi
}

# Never signal a PID just because it is stored in a file. Verify the script and
# token in /proc first, so an old file cannot target a reused unrelated PID.
owned_listener() {
    listener_pid=$(read_first "$STATE_DIR/listener.pid")
    listener_token=$(read_first "$STATE_DIR/session-token")
    is_uint "$listener_pid" && [ "$listener_pid" -gt 1 ] && [ -n "$listener_token" ] || return 1
    [ -r "/proc/$listener_pid/cmdline" ] || return 1
    listener_cmd=$(tr '\000' '\n' < "/proc/$listener_pid/cmdline")
    printf '%s\n' "$listener_cmd" | grep -F -x "$DASHBOARD_DIR/wake-listener.sh" >/dev/null || return 1
    printf '%s\n' "$listener_cmd" | grep -F -x "$listener_token" >/dev/null
}

stop_listener() {
    if owned_listener; then kill -TERM "$listener_pid" 2>/dev/null || :; fi
    # Removing the token invalidates workers immediately, even if TERM delivery
    # is delayed while a system command is in progress.
    rm -f "$STATE_DIR/session-token" "$STATE_DIR/wake-ticket" "$STATE_DIR/native-phase" "$STATE_DIR/listener.pid"
}

start_listener() {
    [ "$WAKE_RESTORE" = 1 ] || { log 'Wake restore disabled pending verified device profile'; return 0; }
    wake_profile_valid || return 1
    if owned_listener; then log 'Wake listener already active'; return 0; fi
    # /tmp is intentional: /mnt/us is commonly FAT and cannot hold FIFOs.
    session_runtime=$(mktemp -d /tmp/kindle-dashboard.XXXXXX) || return 1
    session_token=${session_runtime##*/}
    printf '%s\n' "$session_token" > "$STATE_DIR/session-token"
    printf '%s\n' active > "$STATE_DIR/native-phase"
    sh "$DASHBOARD_DIR/wake-listener.sh" "$session_token" "$session_runtime" </dev/null >/dev/null 2>&1 &
    log 'Started native sleep event listener; no network or power-management writes'
}

# State machine is testable without a Kindle. Only an exit event can authorize
# a restore; outOfScreenSaver alone intentionally never does.
handle_native_event() {
    event_name=$1
    case "$event_name" in
        goingToScreenSaver|readyToSuspend)
            printf '%s\n' sleeping > "$STATE_DIR/native-phase"
            rm -f "$STATE_DIR/wake-ticket"
            log 'Native sleep: dashboard yields display' ;;
        outOfScreenSaver|wakeupFromSuspend)
            printf '%s\n' locked > "$STATE_DIR/native-phase"
            rm -f "$STATE_DIR/wake-ticket"
            log 'Native wake: waiting for lockscreen exit' ;;
        exitingScreenSaver)
            case "$(read_first "$STATE_DIR/native-phase")" in locked|sleeping) ;; *) return 0 ;; esac
            [ -f "$STATE_DIR/active" ] && ! disabled || return 0
            native_unlocked || { log 'Exit event ignored: native lockscreen guard still locked/unknown'; return 0; }
            wake_sequence=$((wake_sequence + 1))
            ticket="$session_token.$wake_sequence"
            printf '%s\n' "$ticket" > "$STATE_DIR/wake-ticket"
            printf '%s\n' restoring > "$STATE_DIR/native-phase"
            queue_restore "$ticket" ;;
    esac
}
