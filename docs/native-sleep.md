# Native suspend and alarm wake: experimental validation

Continuous foreground display and scheduled native sleep are different policies.
The installed Dashboard currently uses an owned `preventScreenSaver` hold while
foreground. A sleeping Kindle cannot run a JavaScript refresh timer. A native RTC
alarm can wake its processor, but does not necessarily dismiss Special Offers or
return a Mesquite app to the foreground. This project will not synthesize an unlock
or draw Dashboard over the ad lockscreen.

## What is available

`test-native-sleep.sh` is a **single-cycle hardware experiment**, disabled by
default. It is not a refresh scheduler and does not download or display images.
There is no automatic boot integration and no periodic alarm loop.

The experiment requests normal native power-button sleep, waits for
`readyToSuspend`, then requests a relative 120-second alarm through
`com.lab126.powerd.rtcWakeup`. It records native events, RTC readback and kernel
suspend/resume evidence. It never writes `/sys/power/state` or an RTC sysfs node,
stops Amazon services, changes CPU governors, or wakes/unlocks the display.
It will not clear another application's sleep inhibitor.

This follows the native sequence used by
[KOReader's Kindle power driver](https://github.com/koreader/koreader/blob/master/frontend/device/kindle/powerd.lua).
In that implementation `rtcWakeup` is set during `readyToSuspend`; alarm resume can
leave powerd in `screenSaver` or `suspended`. No upstream code was copied.

## Evidence on this device

Read-only inspection on 2026-10-10 found:

- Board: `Freescale_i.MX_6SoloLite_based_Wario_Board`, armv7l.
- Firmware build: `002-juno_16020101_muscat_wario-409747`
  (user reports firmware 5.16.2.1.1).
- Native `powerButton` and `rtcWakeup` integer properties are available.
- Three RTC interfaces are present; powerd's platform configuration uses the
  max77696 relative alarm interface. Choosing an arbitrary `/dev/rtcN` is unnecessary.
- Historical kernel logs show `PM: Entering mem sleep` and subsequent resume.

These facts establish native suspend capability, **not** a successful Dashboard
alarm wake. A write accepted by LIPC, a populated alarm, or a `wakeupFromSuspend` event
alone is insufficient. Compare the new kernel transitions, elapsed wall time and
observed absence of user input. A successful one-shot test also does not establish
Wi-Fi reconnection, repeated unattended cycles or battery endurance.

## Run the read-only check

```sh
sh /mnt/us/extensions/dashboard/test-native-sleep.sh --check
```

The command prints the exact detected model, firmware and kernel. It makes no
power changes, and works without enabling the experiment.

## Run one controlled cycle

Be physically near the Kindle. Unplug USB/charging, stop Dashboard normally, and
leave the Kindle unlocked. KOSSH holds `preventScreenSaver` and may terminate SSH
on sleep, so a normal KOSSH session is not a clean sleep-test environment. Do not
clear an unrelated inhibitor simply to make the test pass.

For a prepared test session, put these settings in private `config.local.sh`, using
the **exact values from --check**, not a profile guessed from the product name:

```sh
NATIVE_ALARM_EXPERIMENT=1
NATIVE_ALARM_MODEL="<exact model>"
NATIVE_ALARM_FIRMWARE="<exact firmware build>"
NATIVE_ALARM_KERNEL="<exact uname -r>"
```

With a suitable existing terminal/SSH setup, detach the one-cycle test so losing
the connection does not terminate it:

```sh
nohup sh /mnt/us/extensions/dashboard/test-native-sleep.sh --run </dev/null >/dev/null 2>&1 &
```

Do not press a button or attach USB during the expected alarm window; either can
wake the device and invalidate the result. The expected interval starts when the
native `readyToSuspend` event arrives, not when the script starts. If the device
does not return network access, manually wake and unlock it after the test window,
restart your SSH tool, and inspect `logs/native-sleep-test.txt`. The previous report
is retained as `.1`. The script never claims automatic wake verification itself.

The listener has a bounded wait while the CPU runs. **A shell timeout cannot rescue
a failed hardware wake while the CPU is suspended.** Normal power-button wake is
the recovery path. The native lockscreen remaining visible is expected.

## Stop and recovery

`Stop Dashboard` / `stop.sh` signals only this experiment's verified PID.
`/mnt/us/dashboard-disable` prevents new alarms and ends the experiment at its next
native event. Reopening Dashboard is blocked while the test lock exists.
An already accepted one-shot alarm may still wake the CPU once: `rtcWakeup` is
write-only, and this code does not guess cancellation semantics or clear shared
native alarms. It never establishes a repeating schedule.

Set `NATIVE_ALARM_EXPERIMENT=0` after testing. Wake/unlock normally and reopen
Dashboard to resume the existing foreground policy. If interrupted by a hard
restart, verify the recorded `state/native-sleep-test.lock/pid` is no longer this
script before removing that one stale test lock directory. No system files or
boot settings need restoration.

## Remaining implementation gate

Before a production sleep/refresh loop, verify a physical alarm cycle, network
reconnection after that wake, and native app lifecycle on this firmware. Decide
whether refreshing a cache while ads remain visible meets the intended workflow.
Continuous Dashboard visibility through native ad-lockscreen sleep is not promised.
Until then the installed foreground mode and its refresh schedule stay unchanged.
