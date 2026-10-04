# Exit and recovery

The client never stops Amazon's framework, grabs input, alters the lockscreen,
or registers a boot task. With wake restoration enabled, a session owns a blocking
event subscriber; Stop disarms and terminates it. An active state file alone is
informational and cannot keep the Kindle awake.

## Normal exit

1. Reopen KUAL through your normal launcher.
2. Select Dashboard -> Stop Dashboard. The menu reloads, the active marker is
   removed, wake tickets are invalidated and the owned listener is terminated.
   Navigate to Home/a book normally.
3. If using SSH, run `sh /mnt/us/extensions/dashboard/stop.sh`, then navigate on
   the Kindle to repaint the normal interface. SSH stop deliberately does not
   synthesize key events or write firmware-specific app-launch properties.

Normal power-button sleep/wake is unchanged and can display Amazon's ad
lockscreen. Stop does not blank or replace that lockscreen.

## Disable all dashboard drawing over USB

1. Connect USB. Create an empty `dashboard-disable` file at the USB drive root,
   not inside the extension. Ensure the filename has no `.txt` suffix.
2. Safely eject. Start and refresh now refuse to run. An in-flight fetch rechecks
   the switch before cache promotion/drawing; an already running draw may finish.
   The listener checks the switch on every event and the restore worker checks
   it before drawing. A blocked idle listener exits on Stop or its next event.
3. Select Stop Dashboard or run `stop.sh` over existing SSH. Diagnostics still
   works with the switch present.
4. Remove the file only when ready to resume manual testing. No task runs simply
   because you remove it.

## Interrupted transfer / stale lock

A request normally ends within the configured download deadline (30 seconds by
default), plus device probes, KUAL settle and rendering time. A second action
fails rather than racing the first. Wait for the first action to finish. Check
`logs/dashboard.log` and the PID in `state/action.lock/pid`.

If the PID is still live, do not delete its lock. Use the kill switch and allow
the action to finish. For a confirmed hung dashboard script, a normal `TERM`
through your existing terminal permits its cleanup trap; verify the process
belongs to this extension before signaling it. Hardware driver calls may hang
independently of the HTTP deadline; share diagnostics in that case.

After a normal Kindle restart, or after verifying the recorded PID is no longer
running, remove only this extension's stale lock files:

```sh
cat /mnt/us/extensions/dashboard/state/action.lock/pid
# Verify this PID is absent from `ps` before proceeding.
rm -f /mnt/us/extensions/dashboard/state/action.lock/pid
rmdir /mnt/us/extensions/dashboard/state/action.lock
sh /mnt/us/extensions/dashboard/stop.sh
```

These paths can also be removed over USB after a restart. Do not delete locks
while actions are running. Stop removes leftover temporary transfer files. Save
any `cache/previous.tmp.*` backup first if recovering from a hard power loss during
display; it may contain the previous image. Ordinary signals roll back a pending
cache transaction, but SIGKILL/power loss cannot execute shell traps. Filesystem
durability across an abrupt reset is not guaranteed.

If the normal UI is unresponsive, use the Kindle's normal Settings -> Restart
when possible. A forced restart procedure must match your exact model; consult
its device guide rather than guessing hold times. This project does not change
Amazon's recovery or restart mechanisms.

## Uninstall

Run Stop Dashboard, then remove only `extensions/dashboard/` over USB. Preserve
diagnostics/cache first if wanted. Remove the root `dashboard-disable` marker if
you created it. No system or boot changes need reversal.
