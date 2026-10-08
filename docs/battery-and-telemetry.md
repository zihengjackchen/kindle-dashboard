# Battery measurements and contact telemetry

> Library app update: see [Kindle app](kindle-app.md) and [editor](dashboard-editor.md). The manual KUAL workflow below remains a fallback; its restrictions do not describe the new app timers and touch controls.

The client reads device state only during existing actions. It never wakes to
sample, polls a timer, holds a wake lock, or modifies Wi-Fi/frontlight settings.
Power handling remains native. The optional wake listener blocks on events and
is gated by a verified device profile.

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
  weather/metric grouping as visual inspiration; no WAF/WebSocket dependency.
- [jstriblet](https://github.com/jstriblet/kindle-wall-display): observed battery,
  bounded failures, stale-image preservation, and explicit recovery discipline.

These are independently implemented ideas. No upstream code was copied. We did
not adopt framework shutdown, direct kernel suspend, RTC writes, radio resets,
screensaver inhibition, watchdog respawns or remote self-updates. Hardware-specific
alarm testing belongs after diagnostics, outside this native-sleep release.
