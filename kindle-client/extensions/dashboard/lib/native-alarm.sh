#!/bin/sh
# Native powerd alarm only. No raw RTC/sysfs writes, unlock, or framebuffer access.
# Based on the documented sequence in KOReader's kindle/powerd.lua (not copied).

native_alarm_profile() {
    [ "$NATIVE_ALARM_EXPERIMENT" = 1 ] || { fail 'Native alarm experiment is disabled'; return 1; }
    check_enabled || return 1
    read_device_info
    [ -n "$NATIVE_ALARM_MODEL" ] && [ "$MODEL" = "$NATIVE_ALARM_MODEL" ] &&
        [ -n "$NATIVE_ALARM_FIRMWARE" ] && [ "$FIRMWARE" = "$NATIVE_ALARM_FIRMWARE" ] &&
        [ -n "$NATIVE_ALARM_KERNEL" ] && [ "$(uname -r)" = "$NATIVE_ALARM_KERNEL" ] || {
        fail 'Native alarm profile does not match this model, firmware and kernel'; return 1;
    }
    is_uint "$BATTERY" && [ "$BATTERY" -ge 20 ] || {
        fail 'Native alarm experiment requires a known battery level of at least 20%'; return 1;
    }
    [ "$(external_power)" = 0 ] || {
        fail 'Unplug USB/charging for the suspend experiment; unknown supply state is not accepted'; return 1;
    }
    [ "$(probe lipc-get-prop com.lab126.powerd state)" = active ] || {
        fail 'Unlock Kindle normally before starting the experiment'; return 1;
    }
    [ ! -f "$STATE_DIR/app.pid" ] && [ ! -f "$STATE_DIR/active" ] || {
        fail 'Stop Dashboard before starting the native alarm experiment'; return 1;
    }
    [ "$(probe lipc-get-prop com.lab126.powerd preventScreenSaver)" = 0 ] || {
        fail 'Another app holds preventScreenSaver; this experiment will not clear its hold'; return 1;
    }
    for alarm_command in lipc-get-prop lipc-set-prop "$LIPC_WAIT_BIN" timeout; do
        command -v "$alarm_command" >/dev/null 2>&1 || {
            fail "Native alarm experiment requires $alarm_command"; return 1;
        }
    done
}

native_alarm_arm() {
    # This function must only be called by the readyToSuspend event handler.
    # powerd expects a relative delay, not an epoch or an RTC device number.
    [ "$NATIVE_ALARM_EXPERIMENT" = 1 ] && ! disabled || return 1
    is_uint "$1" && [ "$1" -ge 60 ] && [ "$1" -le 3600 ] || return 1
    [ "$(probe lipc-get-prop com.lab126.powerd state)" = readyToSuspend ] || {
        log 'Native alarm: missed readyToSuspend window; no alarm written'; return 1;
    }
    probe lipc-set-prop -i com.lab126.powerd rtcWakeup "$1" || {
        log 'ERROR native powerd rejected rtcWakeup'; return 1;
    }
    log "Native one-shot alarm accepted delay=${1}s; hardware wake is not yet proven"
}
