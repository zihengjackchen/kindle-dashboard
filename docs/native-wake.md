# Accept native sleep, restore after native lockscreen exit

The session implementation is complete and mock-testable. Its physical Kindle
profile is deliberately **disabled by default** because model, firmware and
lockscreen state semantics have not yet been supplied. It never stops powerd,
changes idle timeout, modifies advertisements, sends wake events, or writes a
suspend request. No boot integration is added.

## Lifecycle

```text
Start -> draw page -> blocking event subscription
native goingToScreenSaver / readyToSuspend -> suppress dashboard drawing
native wake / outOfScreenSaver -> continue waiting; ads may still be visible
exitingScreenSaver + verified unlocked property -> short settle -> recheck
    -> validate and draw last local image, without HTTP or Wi-Fi activity
Stop / kill switch / subscriber failure -> disarm restoration
```

An ordinary event subscriber can remain in memory while the OS suspends; this
implementation holds no power-management inhibitor. Its energy behavior still
needs hardware measurement. It uses `lipc-wait-event -m com.lab126.powerd '*'`
and a private FIFO under `/tmp` (the USB filesystem may not support FIFOs).
There is no polling, timer-based refresh, listener restart loop, or networking in
the restore path. EOF is terminal and suppresses further automatic drawing.

`outOfScreenSaver` is **not** sufficient to draw. An ad-supported device may
still require a swipe/unlock. A confirmed `exitingScreenSaver` event plus a
separate read-only property that actually distinguishes unlocked from locked
state are required. A powerd `active` value alone must not be assumed to do so.
If no such reliable profile is found, use manual refresh; do not weaken the guard.

Each sleep invalidates any pending restore ticket. The worker rechecks session,
ticket, kill switch, phase, model/firmware and lockscreen guard after settling and
immediately before display. Duplicate exit events are ignored. Stop invalidates
tickets before acquiring the drawing lock, then terminates only the listener
whose `/proc` command line matches its script and random session token. The
listener signals only its own children. A restore blocked by another action
skips rather than retrying indefinitely.

## Gather evidence first

1. Run Stop Dashboard. Collect the ordinary diagnostics report.
2. From your existing SSH/terminal, run:

   ```sh
   sh /mnt/us/extensions/dashboard/record-wake-events.sh
   ```

3. During its 90-second capture, use the normal power button to sleep/wake and
   dismiss the ad lockscreen normally. Note the wall-clock time of the swipe.
4. Retrieve `logs/wake-events.txt` and `logs/diagnostics.txt`. The trace only
   observes events and powerd state; it does not change either. Its capture does
   not itself prove a lockscreen-exit guard exists.
5. Review the model/firmware, event order, available read-only properties, and
   choose a property/value that is true **only after** the native lockscreen is
   gone. Validate it through repeated power-button and sleep-cover cycles.

After that review, set the exact observed values in `config.sh`:

```sh
: "${WAKE_RESTORE:=1}"
: "${WAKE_VERIFIED_MODEL:=<exact normalized model from diagnostics>}"
: "${WAKE_VERIFIED_FIRMWARE:=<exact firmware string from diagnostics>}"
: "${WAKE_UNLOCK_SOURCE:=<verified LIPC source>}"
: "${WAKE_UNLOCK_PROPERTY:=<verified read-only property>}"
: "${WAKE_UNLOCK_VALUE:=<value observed only after lockscreen exit>}"
```

These placeholders are not usable configuration; no profile is certified or
bundled. Source/property/value cannot come from the NAS. A firmware mismatch
fails closed. Run Start again after configuration changes. Set `WAKE_RESTORE=0`
and Stop to disable the listener. A failed profile leaves manual use available
after disabling that flag; it does not install a speculative fallback.

## Acceptance on the device

- Ads and normal lock/swipe behavior must remain unchanged.
- No dashboard pixels appear while locked or during native sleep transitions.
- After normal unlock, the last page returns without any network request.
- Sleep again immediately during settling; the pending redraw must be cancelled.
- Stop prevents every subsequent restore, including after a sleep/wake cycle.
- Kill switch suppresses a restore; battery and CPU behavior are measured at idle.
- Reopen KUAL and operate Home/book UI to confirm safe exit and no input capture.

The prototype still does not own a native application window: Amazon UI repaints
can overwrite the dashboard while awake. Direct touchscreen navigation remains
future work. KUAL Next/Previous is the current standalone navigation mechanism.
