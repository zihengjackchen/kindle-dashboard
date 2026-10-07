# Dashboard studio and Kindle controls

Open `http://YOUR_NAS:8080/` in a browser and connect using your dashboard token.
The studio edits the **overview** page; four dedicated detail pages remain available.

The default overview fits the original 12 watchlist instruments, weather with a short
forecast, NAS storage/CPU/memory/alerts, manual notes, and Kindle status on one
screen. It is designed for portrait Paperwhites, including 1072 × 1448.
The current deployment uses the imported mini-ticker list: 20 stocks/ETFs and
BTC/ETH. An optional sixth widget shows [ChatGPT usage](chatgpt-usage.md).

## Customize a page

1. Connect to load the saved preferences and last reported Kindle measurements.
2. Set a title and choose compact or comfortable typography/spacing.
3. Hide or add widgets, move them with the up/down buttons, choose half/full
   width, and select small/medium/large. Adjacent half-width widgets share a row.
   An unpaired half-width widget fills its row. Size sets relative row height.
4. Choose watchlist symbols. Use the wide, large watchlist widget for long lists; choose two or three quote columns.
   Above 12 symbols, rows prioritize price, percentage change and source time;
   absolute price changes remain available on the original detail pages.
5. Add up to five manual notes, each at most 100 characters. Long text can be
   truncated to fit its card; preview before saving. These are not synced calendar events.
6. Select **Preview draft** to render without saving or touching the Kindle.
7. Select **Save to dashboard**, then manually refresh the overview on the Kindle.

The preview resolution affects only the browser. The Kindle continues to send
its actual screen size. Battery and network readings in the editor come from the
selected device's last request, with its last-contact time shown separately.
Previews do not update the server's device-contact history.

Export/import transfers layout JSON, including notes but no tokens. Default
layout resets the draft only. Preferences are shared by all Kindles using this
service; the last save wins. There is no automatic polling or push to the Kindle.
Selecting a detail page in the preview does not change which page the Kindle uses.

Weather location and market provider credentials still belong in the NAS `.env`.
Weather can display both Celsius and Fahrenheit (the default) or the source unit.
The editor selects existing instruments; it does not configure new data providers.
Missing data is labeled, and stale data retains its source timestamp. Current
means current at image generation, not continuously updated while the image sits
on the Kindle. The footer always records image generation time.

## Next, previous, and stop

The displayed PNG is not a touchscreen interface. All buttons live in
**KUAL → Dashboard**:

| Action | Behavior |
| --- | --- |
| Start Dashboard | Fetches the selected page and marks the manual session active. |
| Refresh Dashboard | Fetches and draws the currently selected page once. |
| Refresh All Pages | Fetches five pages so navigation works offline. |
| Next / Previous Dashboard (cached) | Cycles through overview, weather, markets 1, markets 2, NAS, then wraps. No network call. |
| Stop Dashboard | Removes active state, stops an optional verified wake listener, retains the cache, and leaves KUAL open. |

Return to the native interface and reopen KUAL to use these controls. If asleep,
wake and dismiss the normal Amazon lockscreen first. The framework is never
stopped by this app. A native repaint can replace the dashboard at any time.
There is **no automatic rotation** and no touch listener. For one-page use, stay
on overview and use Refresh Dashboard; a timer would add activity without solving
native sleep or lockscreen behavior.

For recovery, connect USB and create `/mnt/us/dashboard-disable` (a file named
`dashboard-disable` at the visible USB root), safely eject, then select Stop
Dashboard in KUAL. The kill switch does not itself erase the framebuffer or stop
already-running shell commands. See [native wake](native-wake.md) for optional
event-driven restoration after a verified lockscreen exit.

The inspected Paperwhite logs showed successful `eips` output at 1072 × 1448,
90% battery, and a successful Stop. Firmware identification remained unknown;
the few samples taken within a minute cannot establish battery drain. Wake
restoration, timed refresh and experimental power behavior remain disabled.

## Persistence and API

Compose sets `DASHBOARD_LAYOUT_PATH=/state/layout.json` in the existing writable
state volume. Preferences are validated, written to a temporary file, flushed,
then atomically replaced. A failed save keeps the old layout. Back up this volume
or export the layout JSON before deleting volumes. Invalid saved JSON falls back
to defaults with a warning.

All editor APIs require a configured `API_TOKEN` and a matching bearer header:

| Endpoint | Result |
| --- | --- |
| `GET /layout` | Saved layout, defaults, allowed tickers, and whether persistence is configured. |
| `PUT /layout` | Validate and save a layout; JSON response is the normalized saved value. |
| `POST /preview.png` | Layout JSON body plus normal image query parameters; render without persistence/contact recording. |

Bodies are limited to 16 KiB. Widgets, dimensions, counts, text lengths and symbols
are bounded; arbitrary templates, paths and executable actions are not accepted.
An unset token disables the editor APIs. An unset layout path permits authenticated
previews but rejects saving. The original image endpoint can still run without a
token for a local development setup. No system, power, trade or Docker control
endpoints were added.

## Verification

Run `python -m pytest server/tests/test_layout.py -q` for persistence, failed-save
recovery, auth, body bounds, invalid layouts, and preview/contact isolation.

The optional browser test runs an isolated local server, not your NAS:

```sh
pip install playwright
playwright install chromium
python scripts/test-editor.py
```

Alternatively set `DASHBOARD_TEST_BROWSER` to an installed Chromium-based browser
executable. The test exercises editing, auth failures, preview/save, export/import,
reload, and mobile sizing. Screenshots go to ignored `.tools/editor-tests/`.
