# Battery measurements and contact telemetry

## Current library app: measured capabilities, not a runtime promise

The app retains Mesquite/WebKit and a loopback HTTP helper while open. The old
20-second browser heartbeat and 10-second supervisor polling are removed. Native
app/power/HAL events wake a blocking supervisor; one 30-second startup check and
30-minute fallback audits cover failed launches and missed events. Events handle
normal exit promptly instead of delaying cleanup for 30 minutes. The heartbeat
was a liveness lease for crash cleanup, never a requirement for the e-ink image.
Its removal means a hung JavaScript page is no longer detected by a 90-second
lease; native crash/exit events and the fallback process checks provide cleanup.
There is no continuous NAS connection, animation, or continuous PNG rendering.

Implemented savings: NAS-side rendering, default hourly refresh, four-hour night
refresh, at least four-hour refresh below 20% when not charging, cached-image
fallback without a tight retry loop, foreground checks, and cleanup on exit.
The app sets the native frontlight level to zero, then restores the previous
level on exit. True LED-off on this Paperwhite has not been established.
Wi-Fi remains under the normal Kindle policy; this client does not deliberately
turn the radio off between image fetches. Automatic page rotation is optional
and switches already-cached images without additional downloads.

Deep suspend, RTC alarms and CPU governor changes are **not implemented**.
`KEEP_AWAKE_PLUGGED=0` remains the default and the installed setting. With normal
sleep enabled, the Amazon lockscreen may replace the app. This is not yet a
validated combination of uninterrupted 24/7 visibility and low battery drain.

The October 9 live audit found KOSSH running
with `preventScreenSaver=1`. KOSSH also redraws its address every three seconds.
That debugging state is unsuitable for a battery benchmark. The device's raw
fuel-gauge attributes have inconsistent-looking units, so no runtime is inferred
from them. Also, `powerd.isUsbConnected` is absent on this firmware: the optional
plugged-in keep-awake detection now supports a verified sysfs alternative. The
candidate is `/sys/class/power_supply/max77696-uic/present`. Do not use the charger
`online` flag: it read 1 while `present` was 0 and the battery reported discharging.
Physical plug/unplug confirmation is required before enabling this device profile.

No unplugged endurance measurement exists for this app. A continuously awake
browser should not be assigned the multi-week claims of a suspended display.
Measure matched 12-24 hour unplugged windows with KOSSH stopped first. If a
window loses D percentage points over H hours, drain is D/H points per hour;
100H/D hours is only a linear full-charge extrapolation, not a warranty. Reject
charging samples and zero-drop windows as insufficient for a lifetime estimate.

The manual KUAL one-shot refresh remains a lighter fallback: it exits after
drawing. See [Kindle app](kindle-app.md) for the interactive mode and native-sleep
boundaries. No automatic battery sampler or background measurement job is added.

Image requests carry the existing battery/charging/geometry/model/page fields.
With `SEND_TELEMETRY=1` (default), these optional fields are also sent:

| Field | Meaning |
| --- | --- |
| `device_id` | Configurable label, default `kindle`; not a serial number |
| `rssi` | Wi-Fi dBm from the first valid wireless interface; absent if unavailable |
| `fetch_seconds` | Previous completed download and validation duration, whole seconds |
| `fetch_failures` | Consecutive failed download/validation attempts before this request |
| `last_success_epoch` | Device-clock time of the previous validated download |

The current request cannot report its own outcome before it completes. Successful
download does not prove the panel displayed it. `/status` records server-clock
`last_seen` upon an authenticated valid image request, even if rendering fails.
Browser previews omit `device_id` and cannot manufacture Kindle contact.
Unknown readings are omitted. No log upload or remote command channel exists.
Set `SEND_TELEMETRY=0` to omit these optional fields; battery/charging remain part
of the core dashboard request.

The server retains at most 32 latest device records in one atomic JSON file.
This is contact metadata, not a database or continuous history. The Docker state
volume preserves it across container replacement. A failed write is logged;
rendering continues with in-memory contact records.

The NAS page separates current contact, previous validated fetch, source time,
and image generation time. An offline cached PNG cannot update its own age or
change its stale badge while asleep. Always read the printed absolute timestamps.

## Compare two overnight windows

1. Charge beforehand and unplug. Keep Wi-Fi, frontlight, duration, room conditions,
   and normal Kindle activity comparable in both windows.
2. Stop Dashboard for a baseline window. Use **Record Battery Sample** at its
   beginning and end; this is a local read and writes `logs/battery.csv`.
3. Copy that CSV to your computer and retain only this window's rows. Repeat for
   an active dashboard window, accepting the normal native sleep/ad screen.
4. Run `python scripts/battery-report.py baseline.csv` and again for dashboard.csv.

The report rejects unknown or charging observations and battery increases.
It reports elapsed hours and percentage points/hour, with no lifetime promise.
Battery percentages are coarse and nonlinear. Two wakeups for the observations
also cost energy. A flat battery reading does not prove successful suspend.
Repeat comparable long windows before attributing a change to dashboard mode.
Logs rotate at the configured size; `.1` is the preceding file.

## What we adopted from the reference projects

- [alexishida](https://github.com/alexishida/kindle-dashboard): browser preview,
  connection checks and off-device rendering as usability patterns.
- [1RandomDev](https://github.com/1RandomDev/kindle-smarthome-dashboard): readable
  weather/metric grouping as visual inspiration. Our app also uses native WAF,
  but has no persistent WebSocket connection. Its README explicitly reports
  rapid battery drain from keeping the device awake with a persistent connection.
- [jstriblet](https://github.com/jstriblet/kindle-wall-display): observed battery,
  bounded failures, stale-image preservation, and explicit recovery discipline.

These are independently implemented ideas. No upstream code was copied. We did
not adopt framework shutdown, direct kernel suspend, RTC writes, radio resets,
watchdog respawns or remote self-updates. A foreground-only plugged-in sleep
inhibitor exists, with event-driven release and a configurable external-power
indicator; hardware acceptance remains required as noted above. Jstriblet's main battery advantage is suspend-to-RAM plus RTC wake; its
screen takeover also stops the native GUI. Those are materially different from
our interactive app and cannot be enabled here by copying a sleep command.

### Investigation on 2026-10-10

SSH reconnected successfully. The installed keep-awake flag was still disabled.
The device reported discharging, `battStateInfo.usb=false`, and charger/uic
`present=0`. Charger `online=1` was still misleading and is not used. This firmware
does not expose `isUsbConnected`; the client now falls back to the named USB
boolean in `battStateInfo`. Firmware identification also reads `/etc/version.txt`.
The observed build was `juno_16020101_muscat_wario` (user-reported 5.16.2.1.1).

Power telemetry now includes external power, the shared native sleep hold, and
the configured policy. Unknown external power allows native sleep. An existing
hold owned by an SSH tool is not claimed by Dashboard. The supervisor can now
reassert its own hold if it is cleared, and records native sleep/wake and foreground
changes to make subsequent unexpected exits diagnosable.

RTC interfaces exist, but no alarm or raw suspend test was executed. Their
presence alone does not establish wake reliability or ad-lockscreen behavior.
The foreground refresh timer remains separate from scheduled hardware wake.
No battery-runtime estimate is claimed while SSH itself holds the device awake.
