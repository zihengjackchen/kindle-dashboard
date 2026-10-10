# Kindle library app

The Dashboard library scriptlet follows the same Mesquite registration pattern as
[KWordle](https://github.com/crizmo/KWordle). It is independently implemented here;
it does not embed Wordle or KOReader. The owner reports KWordle working on firmware
5.16.2.1.1. Document launch, navigation, exit, and reopening are verified there.

## Install

1. Extract the configured private client ZIP into the Kindle USB root. Merge both
   `documents/` and `extensions/`; keep your existing `config.local.sh` when using
   the public ZIP. The private ZIP contains the NAS bearer token: do not publish it.
   `documents/Dashboard.sh` embeds an original grayscale library cover using the
   scriptlet `# Icon:` field. Regenerate it with `python scripts/build-cover.py`
   (Pillow and DejaVu Sans or Windows Segoe UI required). Artwork is retained in
   `docs/assets/dashboard-cover.png`. USB eject normally triggers indexing; over
   SSH, this device accepts `lipc-set-prop com.lab126.scanner reScanFile
   /mnt/us/documents/Dashboard.sh` to refresh only this document.
   The cover matches the installed KWordle image format: **454 x 694, RGB PNG**,
   with grayscale artwork and space for Kindle's progress badge.
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

Previous/Next switch cached pages immediately without any network request. Refresh
fetches every configured page in one bundle. The top native **X** returns Home;
the session supervisor then restores light/power settings and stops the bridge.
The supervisor waits for native app/power events, checking `appmgrd.activeApp`
when they arrive. There is no browser heartbeat or ten-second polling loop. A
one-time 30-second startup check catches failed launches; the fallback audit runs
every 30 minutes. Listener failure ends the session and restores normal power.
Cleanup unloads this app's WebKit instance so reopening gets a fresh session.
KUAL Stop signals the supervisor directly; blocking event waits and timer children
are interruptible. The existing bounded cleanup wait prevents a reopening race.

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
through `powerd.preventScreenSaver`, while external power is detected. Firmware
5.16.2.1.1 lacks `powerd.isUsbConnected`; set `VERIFIED_EXTERNAL_POWER_PATH` to a
plug/unplug-tested sysfs indicator instead. On the inspected device,
`max77696-charger/online` is 1 even with USB `present` at 0: do not use that online
field. The candidate `/sys/class/power_supply/max77696-uic/present` still needs a
physical plug/unplug check before enabling the installed option.

The supervisor watches appmgrd, powerd and HAL events. It releases its inhibitor
on unplug, leaving the app, manual power-button events, native sleep, Stop or kill
switch detection. An inhibitor already held by another program is not claimed or
reset. A 30-minute audit is only a fallback; normal exit/unplug handling is event
based. Manual sleep is not undone automatically; wake lifecycle/events restore
normal dashboard operation. The power button and unplug sequence require physical
acceptance with KOSSH stopped, because KOSSH itself inhibits sleep. `activeApp` must match this app
and `powerd.state` must be `active`; unknown values fail closed. This controls an
open app session; it does not unload ads, draw on the lockscreen, or modify Special
Offers. It uses more power than native suspend. Do not advertise 24/7 visibility
until an overnight plugged-in test and unplug/Close recovery test pass.

Run KUAL **Show Diagnostics**, then provide `logs/diagnostics.txt` and
`logs/dashboard.log`. Also report whether the light is completely dark at entry,
whether native Close returns correctly, and what happens after unplugging and
pressing the power button. A screenshot/photo cannot establish the power state.

## Local bridge and cache

The library app measures its image container after the native header and its
own navigation/status rows take their space. Binary requests send this geometry
as the authenticated `X-Dashboard-Viewport: WIDTHxHEIGHT` loopback header. The
shell accepts only dimensions 320-2560 and passes them to the NAS using the
existing `width`/`height` query parameters. Thus Pillow lays out the page at the
app's aspect ratio; it is not a full-panel wallpaper squeezed into the window.
On this Paperwhite the measured image area is **1056 x 1162**, versus the panel's
1072 x 1448. Those numbers are observed, not hardcoded. Resize events trigger a
new render only when geometry changes. Legacy Mesquite's misleading pixel-density
multiplier is ignored because its CSS coordinates already match panel pixels.

The three app controls sit at the top: **Previous / Refresh / Next**. Use the
Kindle's native **X** in the title bar to exit. The dashboard fills the area below
those controls; no status row or bottom row is reserved. The Refresh button shows
progress while fetching, then returns to its normal label. Errors are temporary
8-second overlays. A plain opening message is shown during launch and a white
loading view appears until cached content is ready.

Each refresh makes **one NAS request** to `/dashboard-bundle.json`, including the
measured viewport and device telemetry. The JSON response contains every configured
page as a base64 PNG, page names/order, refresh settings, and one generation time.
The NAS reads the layout and data snapshot once for a consistent set. No separate
settings request is needed. Navigation switches images already in browser memory;
it does not contact the NAS or postpone the next scheduled refresh.

The complete bundle is retained in `cache/app/bundle.json`, separate from the
full-panel KUAL cache. Download goes to a temporary file, with HTTP status, content
type, deadline and an 8 MiB size limit checked. It becomes `bundle.pending`, while
the good bundle remains intact. Mesquite parses the schema and decodes every PNG,
checking dimensions, before acknowledging the pending file's checksum. Only that
acknowledgement atomically replaces `bundle.json`. A damaged image rejects the
whole update. At most one good and one pending bundle are retained.

Opening the app reads the local bundle first, then attempts a refresh. Failure
retains all old pages and their original timestamps, with a brief offline notice after a failed refresh.
Older per-page caches are a first-upgrade fallback when no bundle exists. Legacy
framebuffer KUAL refresh/navigation still use their separate per-page workflow.

A compatible BusyBox HTTP daemon binds **127.0.0.1:18765 only**, while the app is
open. The app manifest points at an unguessable session directory on that origin,
serving the app assets. This device also resolves JavaScript from its native app
directory; authenticated loopback requests were verified on 5.16.2.1.1.
No CORS grant is sent. CGI actions
require POST plus a random per-session header; NAS credentials never enter the
HTML/JavaScript. Only fixed page IDs and actions are accepted. There is no generic
shell-command, filesystem, NAS control, or arbitrary URL endpoint.

## Exit and recovery

1. Use the native **X** in the app's top title bar. KUAL **Stop Dashboard** is a fallback.
2. Via SSH: `sh /mnt/us/extensions/dashboard/stop.sh`.
3. Via USB: create an empty `/mnt/us/dashboard-disable` (USB-root
   `dashboard-disable`). The session exits on the next native event or fallback audit (up to 30 minutes).
   Use Stop/SSH for immediate recovery. If asleep, it processes this after wake. Remove the file only after recovery.
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

## Crash troubleshooting

On firmware 5.16.2.1.1, an earlier manifest enabled native tap recognition without
initializing the `gestures` API. The device logged `EventsHandler::dispatchTapEvent`
followed by a Mesquite segmentation fault. The manifest now declares that API,
as the installed KWordle does. The owner verified Next, Close, and reopening after
this change. Ordinary browser click tests cannot reproduce this native crash.

A separate document-launch failure appeared as `CancellingLOADOperationForApp`:
shell integration returned Home while Dashboard was loading. Both launch entry
points now detach the worker, wait three seconds, and wait up to ten additional
seconds for shell integration/KUAL to leave the foreground before starting the UI.
The worker rechecks the kill switch before making changes. There is no retry loop.

If another crash occurs, preserve the timestamped `mesquite_*.core` in the USB root
and its matching crash report under `documents/`. These are Kindle-generated files;
they may contain device/session data and should not be committed or posted publicly.
Run Stop Dashboard before reopening after a crash. Dashboard's startup and activity
logs are in `extensions/dashboard/logs/`.
