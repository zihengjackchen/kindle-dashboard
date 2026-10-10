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
   BusyBox `httpd` with CGI support. Stock Kindle BusyBox often lacks `httpd`;
   see the helper installation below. Failures are recorded in
   `logs/dashboard.log`, `logs/startup.log`, and `logs/httpd-probe.txt`, with a
   short on-screen notice when the Kindle is awake.
4. A reversible entry is registered for `org.kindledashboard.app` in
   `/var/local/appreg.db`. Its manifest lives in
   `/var/local/mesquite/org.kindledashboard.app/`. No boot or lockscreen files change.
   Mesquite runs as `framework`: the app directory belongs to that user with
   mode 0755, and UI assets have mode 0644. The generated `session.js` is also
   installed there because this firmware resolves script assets locally even
   with an HTTP content URL. It contains only the short-lived loopback session
   key; NAS credentials remain in the shell client.

### HTTP helper for legacy ARM Kindles

The October 9 device log showed `App requires BusyBox httpd with CGI support`.
Both launch routes stopped at this dependency check, before contacting the NAS.
The launcher now tries `extensions/dashboard/bin/busybox`, system BusyBox, then
an already-installed USBNet BusyBox. An explicit `BUSYBOX_BIN` overrides detection.
The probe report retains loader errors as well as missing-applet errors.

For this ARMv7 Paperwhite on 5.16.2.1.1, prepare NiLuJe's published K5 helper on
your computer (Python 3 required):

```sh
python scripts/prepare-httpd.py
```

Copy the three files in `dist/private/httpd-helper/` into the Kindle's
`extensions/dashboard/bin/`. The script checks pinned archive and executable
SHA256 hashes and extracts only the prebuilt helper plus credits. It never runs
the USBNetwork installer or replaces system BusyBox. It does not compile anything.
Keep the helper in the private installation; public source/client releases omit
the binary. Other architectures, including newer armhf Kindles, need their own
verified compatible helper. The loopback CGI self-check runs on every launch.

To include it in a private USB installation ZIP:

```sh
python scripts/package-client.py --httpd-helper-dir dist/private/httpd-helper --output dist/private/kindle-dashboard-client.zip
```

Safely eject USB before launching. If it still closes, reconnect and inspect the
three logs above. Host tests cannot verify the Kindle dynamic loader or Mesquite;
a successful on-device launch remains required.

## Controls and refresh

Previous/Next show cached pages immediately and request an update. Refresh fetches
the current page. Close revokes the local session, restores light/power settings
and asks the native app manager to open Home. The system chromebar also has Close.
The session supervisor detects leaving the app through `appmgrd.activeApp` when
available; otherwise lifecycle callbacks and a 90-second heartbeat lease stop it.
Cleanup unloads this app's WebKit instance so reopening gets a fresh session.
KUAL Stop waits up to 12 seconds for the supervisor's current sleep and cleanup
to finish; it does not reuse a stopping session.

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

A compatible BusyBox HTTP daemon binds **127.0.0.1:18765 only**, while the app is
open. The app manifest points at an unguessable session directory on that origin,
serving the app assets. This device also resolves JavaScript from its native app
directory; authenticated loopback requests were verified on 5.16.2.1.1.
No CORS grant is sent. CGI actions
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
