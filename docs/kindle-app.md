# Kindle library app

The Dashboard library scriptlet follows the same Mesquite registration pattern as
[KWordle](https://github.com/crizmo/KWordle). It is independently implemented here;
it does not embed Wordle or KOReader. The owner reports KWordle working on firmware
5.16.2.1.1. Dashboard itself still requires an on-device acceptance test.

## Install

1. Extract the configured private client ZIP into the Kindle USB root. Merge both
   `documents/` and `extensions/`; keep your existing `config.local.sh` when using
   the public ZIP. The private ZIP contains the NAS bearer token: do not publish it.
2. Safely eject. Open **Dashboard** in the library, like KWordle. KUAL's
   **Start Dashboard** launches the same app. Existing Refresh/Next/Previous items
   remain a framebuffer fallback.
3. First launch checks for existing `mesquite`, `sqlite3`, `curl`, `cksum`, and
   BusyBox `httpd` with CGI support. No compiled binary is downloaded or bundled.
   A missing capability is logged to `extensions/dashboard/logs/dashboard.log`.
4. A reversible entry is registered for `org.kindledashboard.app` in
   `/var/local/appreg.db`. Its manifest lives in
   `/var/local/mesquite/org.kindledashboard.app/`. No boot or lockscreen files change.

## Controls and refresh

Previous/Next show cached pages immediately and request an update. Refresh fetches
the current page. Close revokes the local session, restores light/power settings
and asks the native app manager to open Home. The system chromebar also has Close.
The session supervisor detects leaving the app through `appmgrd.activeApp` when
available; otherwise lifecycle callbacks and a 90-second heartbeat lease stop it.

The web editor sets page names/order, refresh interval (60 minutes by default),
night interval (240 minutes, 22:00–07:00 on the Kindle clock), and optional page
rotation (off by default). Under 20% battery without charging, refresh is at least
four-hourly. These are app timers, not RTC wake alarms. No network fetch is allowed
unless the native foreground/unlocked guard succeeds. Settings are reloaded on
each fetch. Native sleep remains available; cached restoration on resume depends
on the firmware delivering app lifecycle events.

## Frontlight and continuous display: hardware acceptance required

Entry reads/saves `powerd.flIntensity`, then sets zero. On older Paperwhites zero
may mean a faint light. **True off is not claimed until checked on this device.**
The diagnostic report lists readable `/sys/class/backlight/*/brightness` files.
After confirming the hardware path and actual light behavior, set
`VERIFIED_FRONTLIGHT_PATH` in `config.local.sh`. The script saves/restores both raw
brightness and the native level. No arbitrary sysfs discovery writes occur.

`KEEP_AWAKE_PLUGGED=0` is deliberately the shipped default. After observing the
exact properties on the device, `1` enables a reversible foreground-only request
through `powerd.preventScreenSaver`, while `powerd.isUsbConnected` reports external
power. It saves the old value and releases it on unplug, leaving the app, native
sleep, Close, Stop, kill switch or expired session. `activeApp` must match this app
and `powerd.state` must be `active`; unknown values fail closed. This controls an
open app session; it does not unload ads, draw on the lockscreen, or modify Special
Offers. It uses more power than native suspend. Do not advertise 24/7 visibility
until an overnight plugged-in test and unplug/Close recovery test pass.

Run KUAL **Show Diagnostics**, then provide `logs/diagnostics.txt` and
`logs/dashboard.log`. Also report whether the light is completely dark at entry,
whether native Close returns correctly, and what happens after unplugging and
pressing the power button. A screenshot/photo cannot establish the power state.

## Local bridge and cache

An existing BusyBox HTTP daemon binds **127.0.0.1:18765 only**, while the app is
open. The app manifest points at an unguessable session directory on that origin,
avoiding file-URL CORS problems in old WebKit. No CORS grant is sent. CGI actions
require POST plus a random per-session header; NAS credentials never enter the
HTML/JavaScript. Only fixed page IDs and actions are accepted. There is no generic
shell-command, filesystem, NAS control, or arbitrary URL endpoint.

The shell downloads/validates a PNG into a pending file. The app decodes it before
acknowledging its checksum; only then does the shell atomically replace that
page's good cache. Authentication/HTTP/decode failures retain the earlier image.
Old images retain their original timestamp. A stale/source warning appears only
when needed. Disk logs rotate; there are at most five cached and five pending PNGs.

## Exit and recovery

1. Use the app's Close button or native Close. KUAL **Stop Dashboard** is a fallback.
2. Via SSH: `sh /mnt/us/extensions/dashboard/stop.sh`.
3. Via USB: create an empty `/mnt/us/dashboard-disable` (USB-root
   `dashboard-disable`). The session exits on its next supervisor tick. If asleep,
   it processes this after wake. Remove the file only after recovery.
4. If a crashed process left `state/app.pid`/`state/app.lock`, run Stop first.
   Check that the recorded PID is not a running `app-session.sh` before removing
   these stale files/directories. Never signal an arbitrary saved PID.
5. Normal Kindle restart remains available; no automatic dashboard launch occurs.
   After restart, Stop restores persisted light/power state where possible.

To unregister only this app, run `sh /mnt/us/extensions/dashboard/app-uninstall.sh`,
then remove `documents/Dashboard.sh`. KUAL's manual renderer/cache remain usable.

The bridge self-check, browser tests and shell mocks do not substitute for Kindle
hardware testing: firmware API availability, native app manifest handling, full
refresh/ghosting behavior, true light-off, and continuous-display power behavior
remain explicit acceptance checks.
