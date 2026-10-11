#!/bin/sh
# Explicit one-cycle experiment, not a periodic scheduler. Default is read-only.
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$DASHBOARD_DIR/lib/client.sh"
. "$DASHBOARD_DIR/lib/native-alarm.sh"

snapshot() {
    printf 'time='; date -u '+%Y-%m-%dT%H:%M:%SZ'
    printf 'epoch='; date +%s
    printf 'uptime='; cat /proc/uptime
    printf 'powerd.state='; probe lipc-get-prop com.lab126.powerd state
    printf 'preventScreenSaver='; probe lipc-get-prop com.lab126.powerd preventScreenSaver
    cat /proc/driver/rtc 2>/dev/null
    for rtc in /sys/class/rtc/rtc*; do
        printf '%s name=' "$rtc"; cat "$rtc/name" 2>/dev/null
        printf 'wakealarm='; cat "$rtc/wakealarm" 2>/dev/null; printf '\n'
    done
    # Kernel evidence distinguishes actual mem suspend from merely showing ads.
    dmesg 2>/dev/null | grep -E 'PM:|rtc_resume|fg (suspend|resume)' | tail -n 35
}

case "${1:---check}" in
    --check)
        read_device_info
        printf 'model=%s\nfirmware=%s\nkernel=%s\n' "$MODEL" "$FIRMWARE" "$(uname -r)"
        snapshot
        printf '\nRead-only check. No sleep or alarm requested.\n'
        exit 0 ;;
    --run) ;;
    *) printf 'Usage: test-native-sleep.sh [--check|--run]\n' >&2; exit 2 ;;
esac
native_alarm_profile || exit 1
mkdir "$STATE_DIR/native-sleep-test.lock" 2>/dev/null || {
    fail 'Native sleep test already running or stale lock exists'; exit 1;
}
RUNTIME='' EVENT_PID='' TEST_ARMED=0
REPORT=$LOG_DIR/native-sleep-test.txt
# Invoked by the EXIT trap below (older ShellCheck versions miss numeric trap 0).
# shellcheck disable=SC2317,SC2329
test_cleanup() {
    [ -z "$EVENT_PID" ] || kill "$EVENT_PID" 2>/dev/null || :
    if [ -n "$RUNTIME" ]; then
        rm -f "$RUNTIME/events"; rmdir "$RUNTIME" 2>/dev/null || :
    fi
    rm -f "$STATE_DIR/native-sleep-test.lock/pid"
    rmdir "$STATE_DIR/native-sleep-test.lock" 2>/dev/null || :
    # rtcWakeup is write-only and native alarms may be shared. Never clear a
    # raw RTC or guess a cancellation value. An accepted alarm can fire once.
    log "Native sleep test finished armed=$TEST_ARMED; no unlock or display requested"
}
trap test_cleanup 0
trap 'exit 130' INT
trap 'exit 143' TERM HUP
printf '%s\n' "$$" > "$STATE_DIR/native-sleep-test.lock/pid"
[ ! -f "$REPORT" ] || mv -f "$REPORT" "$REPORT.1"
exec > "$REPORT" 2>&1
printf 'Native sleep / 120-second alarm experiment (not a scheduler)\n'
printf 'model=%s\nfirmware=%s\nkernel=%s\n' "$MODEL" "$FIRMWARE" "$(uname -r)"
printf 'Before:\n'; snapshot
RUNTIME=$(mktemp -d /tmp/dashboard-alarm.XXXXXX) || exit 1
mkfifo "$RUNTIME/events" || exit 1
exec 3<> "$RUNTIME/events"
(
    event_child=
    trap '[ -z "$event_child" ] || kill "$event_child" 2>/dev/null; exit 0' TERM INT HUP
    "$LIPC_WAIT_BIN" -m -s 300 com.lab126.powerd '*' >&3 2>/dev/null &
    event_child=$!
    wait "$event_child"
    printf 'listener-ended\n' >&3
) &
EVENT_PID=$!
# Let the subscription connect before requesting the native button transition.
sleep 1
check_enabled && [ "$(probe lipc-get-prop com.lab126.powerd state)" = active ] || exit 1
log 'Native sleep experiment: requesting normal power-button sleep; SSH may disconnect'
probe lipc-set-prop -i com.lab126.powerd powerButton 1 || exit 1
while IFS= read -r event <&3; do
    [ "$(wc -c < "$REPORT")" -lt 65536 ] || { log 'ERROR native sleep report reached size limit'; exit 1; }
    printf '%s event=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$event"
    check_enabled || exit 1
    case "${event%% *}" in
        readyToSuspend)
            # Exactly one alarm per experiment; unrelated later transitions
            # cannot repeatedly postpone it or create an automatic wake loop.
            if [ "$TEST_ARMED" = 0 ]; then
                # A foreground launch, new inhibitor or stop cancels the test.
                [ ! -f "$STATE_DIR/app.pid" ] &&
                    [ "$(probe lipc-get-prop com.lab126.powerd preventScreenSaver)" = 0 ] || exit 1
                native_alarm_arm 120 || exit 1
                TEST_ARMED=1
                printf 'alarm_accepted_epoch=%s delay_seconds=120\n' "$(date +%s)"
                printf 'After alarm acceptance (not proof of suspend):\n'
                snapshot
            fi ;;
        wakeupFromSuspend|resuming)
            [ "$TEST_ARMED" = 1 ] || continue
            printf 'Resume observed; inspecting evidence after native state settles.\n'
            sleep 5
            snapshot
            printf 'RESULT: resume observed. Compare timestamps and new kernel suspend/resume entries; a manual wake is not proof of an alarm wake.\n'
            exit 0 ;;
        outOfScreenSaver|exitingScreenSaver)
            printf 'RESULT: interactive wake/unlock observed; automatic alarm wake is unproven.\n'
            snapshot
            exit 3 ;;
        listener-ended)
            printf 'RESULT: listener ended without a verified alarm wake. A process timeout cannot wake suspended hardware.\n'
            snapshot
            exit 4 ;;
    esac
done
exit 1
