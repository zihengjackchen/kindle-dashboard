# Kindle Dashboard

A Kindle library app and NAS-rendered grayscale dashboard. Open **Dashboard** like
KWordle, use **Previous / Refresh / Next** at the top and the native **X** to exit, and customize the pages in your
NAS browser. Amazon Special Offers and its normal lockscreen remain untouched.

**Existing deployment:** http://192.168.1.8:8080/ — use your dashboard token.

## Install and use

- NAS: follow [setup](docs/setup.md), then run
  `docker compose -p kindle-dashboard --profile live up -d --build` in `server/`.
- Kindle: extract the configured private ZIP into the USB root, merging both
  `documents/` and `extensions/`. Safely eject, then open Dashboard in the library.
- The library app uses Mesquite, sqlite3, curl and BusyBox httpd/CGI.
  Stock Kindle BusyBox may lack httpd: the private installation includes a
  verified upstream helper. Public ZIP users should follow the
  [helper setup](docs/kindle-app.md#http-helper-for-legacy-arm-kindles).
- [Kindle app installation, power behavior and recovery](docs/kindle-app.md)
- [Dashboard editor](docs/dashboard-editor.md)
- [Requested features and remaining work](docs/feature-status.md)

## Included

- Five customizable dashboard pages with names and ordering.
- One NAS request per app refresh downloads all configured pages and settings;
  Previous/Next are instant local cache switches, including offline.
- Weather in Celsius and Fahrenheit, configurable watchlists, NAS metrics,
  Backblaze Cloud Sync status, Kindle telemetry and manual notes.
- Drag-and-drop widget order, half/full width, three height choices, per-widget
  field selection, automatic PNG preview, save/discard/reset and JSON import/export.
- Up to twelve widget instances per page, explicit row/column placement, custom
  titles, independent watchlists and backup-job selection.
- Markdown cards with headings, bold, lists and code; long content shrinks or
  truncates inside its card. Rendering remains entirely on the NAS.
- A quiet grayscale layout: no branding header, repeated quote timestamps, source
  lists or ChatGPT usage. One timestamp and exception-only freshness warnings.
- App refresh timer: 60 minutes normally, four hours at night or low battery;
  configurable in the editor. Optional timed page rotation is off initially.
- Frontlight level saved and set to zero on entry; previous level restored on exit.
- Native event supervision with a 30-minute fallback audit; no browser heartbeat.
- Refresh progress stays in the button; no permanent status row. Plain launch feedback.
- Authenticated downloads, bounded PNG validation, decode-before-commit all-page cache,
  retained stale images on failure, bounded logs, Stop and USB kill switch.
- KUAL manual framebuffer refresh and cached navigation remain fallback tools.

## Hardware status and power boundaries

Installed and tested on a **1072 × 1448 Paperwhite, firmware 5.16.2.1.1**.
The owner confirmed document launch, Next, Close, and reopening after the tap
crash and launcher handoff fixes. The local bridge fetches and displays NAS images
at the measured app canvas size. True light-off, overnight power consumption,
and overnight continuous-display endurance still require hardware measurement.

Older Paperwhites can remain faintly lit at native brightness zero. True off uses
only a diagnostic-confirmed brightness path. The installed device now uses
`KEEP_AWAKE_ON_BATTERY=1`: Dashboard holds off idle sleep while its native window
is foreground, on battery or USB. Public defaults remain opt-in. Native X/Stop
releases the hold; a real power-button sleep is respected. Plugged-only mode is
also available through `KEEP_AWAKE_PLUGGED=1` with the battery flag off. No raw
suspend, scheduled RTC wake, boot changes or ad-lockscreen replacement is installed.
Ordinary app timers do not wake a suspended Kindle. See [power behavior](docs/kindle-app.md).

## Architecture

```text
Dashboard library scriptlet / KUAL
  -> Mesquite app: cached images + top Previous / Refresh / Next + native X
  -> loopback-only, per-session authenticated shell CGI
  -> device telemetry + bounded HTTP request to NAS
NAS collectors -> persisted source snapshots
  -> FastAPI -> bundle of Pillow grayscale PNGs + settings
Kindle -> validate -> decode all pages -> atomic bundle cache -> local navigation
```

The bridge runs only for the app session and exposes fixed actions, never arbitrary
commands or URLs. NAS credentials stay in the shell config. The renderer container
has no Docker socket or host administration credentials. A read-only host exporter
feeds sanitized TrueNAS metrics and Cloud Sync job summaries to it.

## Configuration and data

Configure `DASHBOARD_URL`, `API_TOKEN` and hardware overrides in the Kindle's
`extensions/dashboard/config.local.sh`. Server credentials/location live in private
`server/.env`; layout preferences live in the persistent `/state/layout.json`.
Never publish configured ZIPs or `.env` files.

The Kindle reports battery/charging, screen dimensions, model, firmware and optional
RSSI, free storage, uptime, light level and previous-fetch results. Unsupported
fields are omitted. The NAS collects weather and quotes independently; rendering
never waits on providers. Source timestamps survive failed collections. Cached
images retain their generation time. ChatGPT/Codex usage is no longer collected.

Backblaze status is from TrueNAS Cloud Sync jobs, not an invented backup success
signal. The exporter retains the last observed successful run across later failures;
older history predating the exporter may be unknown. Metrics unavailable on a NAS
version display as unavailable. See [server README](server/README.md).

## Exit and recovery

Use the native **X** at the top or **Stop Dashboard** in KUAL. From SSH:
`sh /mnt/us/extensions/dashboard/stop.sh`.
Create an empty file named `dashboard-disable` at the USB root to revoke the app
session and prevent launching. Normal Kindle restart remains available. No startup
task reopens the app. [Recovery details](docs/kindle-app.md#exit-and-recovery).

## Development and tests

```sh
python -m pip install -r server/requirements-dev.txt
python -m pytest -q
python scripts/test-editor.py
python scripts/test-kindle-app.py
python scripts/package-client.py
```

Browser tests need `pip install playwright` and `playwright install chromium`;
`DASHBOARD_TEST_BROWSER` can select an installed Edge
or Chromium. Shell tests run on Linux or Git Bash with mocked hardware and real
HTTP. Run ShellCheck on the shell scripts and app CGI. The Docker image packages
DejaVu fonts. Examples under `docs/previews/` are explicitly labeled sample data.

## Troubleshooting

- Launch fails: run KUAL Show Diagnostics and read `logs/dashboard.log`; check
  Mesquite/sqlite3/curl and BusyBox httpd CGI support.
- Allow a few seconds after selecting Dashboard: the launcher must return before
  the native app starts. See [crash troubleshooting](docs/kindle-app.md#crash-troubleshooting)
  if tapping crashes the app or a launch immediately returns Home.
- Refresh paused: inspect `appmgrd.activeApp` and `powerd.state` in the diagnostic
  report; do not bypass the lockscreen/foreground guard.
- Old image: check Wi-Fi, NAS reachability, bearer token and source freshness in
  the editor's diagnostic panel. Failure intentionally retains the cache.
- Dim glow: native level zero may not mean true off; verify the hardware path.
- Idle sleep while Dashboard is open: check `KEEP_AWAKE_ON_BATTERY` and the last reported power policy. Close/reopen after changing local configuration.
- No Backblaze widget data: run the host exporter and check the Cloud Sync task.

MIT license for this project's code. External projects are references; see
[references](docs/references.md). Brokerage access, investment signals and RTC wake
scheduling remain outside this release.
