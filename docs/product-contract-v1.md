# Dashboard product and data contract — proposed v1

Status: v1 target design, recorded 2026-10-01. The current `/dashboard.png` endpoint
now implements overview, weather, markets-1, markets-2 and NAS pages from validated
persisted snapshots. Offline KUAL navigation and a guarded native-wake listener
are implemented. Optional richer telemetry, NAS-side weather/market/crypto
collectors and a TrueNAS host exporter are implemented as of 2026-10-04; see
setup.md and battery-and-telemetry.md for the current unversioned contract.
Versioned endpoints, portfolio access and touch navigation are not implemented.
Hardware activation remains gated on diagnostics. See native-wake.md.

## Responsibilities

The Kindle owns device readings, local image storage, manual navigation and
request initiation. The NAS owns weather location, watchlist, data-provider
credentials, collection, timestamps, freshness decisions and all page rendering.
The Kindle never connects directly to a broker, weather provider, market-data
provider, or TrueNAS management API.

```text
Weather / market data / optional portfolio / optional NAS metrics
                           |
                 NAS collectors + persistent snapshots
                           |
                 NAS grayscale page renderer
                           |
                 short authenticated HTTP request
                           |
             Kindle validated cache -> display / page navigation
```

NAS collection and Kindle refresh are independent. A page turn reads an existing
local page and does not start Wi-Fi, contact the NAS, or update market data.
Refreshing data is a separate explicit action. No timed page rotation initially.

## Pages and watchlist

Default proposed page order:

| Page ID | Contents |
| --- | --- |
| `overview` | Weather and selected watchlist summaries plus NAS status |
| `weather` | Current/forecast conditions, high/low, precipitation, short forecast; location and units configured on NAS |
| `markets-1` | S&P 500, VOO, VGT, META, AMZN, GOOG |
| `markets-2` | AMD, PYPL, SOFI, GRAB, BTC-USD, ETH-USD |
| `nas` | TrueNAS health, storage/pool usage, alerts and selected system metrics when available |

Future opt-in pages: `portfolio` and `research`. Six instruments per markets page
keeps text readable on smaller Paperwhites. A denser layout can be added after
checking physical resolution. White background, black text, explicit +/- and
up/down indicators; no dependence on red/green color. Every page includes its
name, page number/count, image generation time and relevant source times.

The watchlist was transcribed from the supplied screenshot. Screenshot prices
are not market data and must never become live values or a test for current
prices. `docs/watchlist.example.json` stores provider-independent IDs and display
labels; it is not yet wired into the server.

S&P 500 is an index, not an equity ticker or a substitute ETF. A provider adapter
must resolve the index explicitly or show unavailable; never silently replace it
with VOO or SPY. GOOG must not silently become GOOGL. Crypto pairs are denominated
in USD. Provider-specific symbols belong inside adapters.

Each quote carries instrument ID, price, currency, absolute change, percentage
change, change basis, market session, source name, source time, fetched time, and
any known delay. Equities/ETFs default to change versus previous regular-session
close; crypto uses an explicitly labeled rolling 24-hour change. Never mix these
definitions behind an unlabeled percentage. Closed markets and delayed quotes
must be identifiable. Quote timestamps can differ within the same page.

## Kindle -> NAS

Cheap available telemetry is useful; a full diagnostic report on every refresh
is wasteful. All optional readings are best-effort and capability-dependent.
Missing means unknown, never a fabricated zero. Unchanged static properties need
not be resent every time unless the server needs them to interpret a request.

| Field | Purpose and policy |
| --- | --- |
| `profile` | Named NAS-owned page/watchlist/location configuration, default `home` |
| `page` | Explicit page ID, required for a single-image request |
| `width`, `height` | Current physical display pixels; required, each 320..2560 |
| `battery` | Optional integer percentage, 0..100 |
| `charging` | Optional 0/1 for actively charging; independent of external-power presence |
| `device` | Optional normalized model label, not serial number |
| `client_id` | Optional user-assigned alias such as `desk-kindle`, not a hardware identifier |
| `firmware`, `arch`, `client_version` | Optional static compatibility metadata |
| `display_backend` | Optional `fbink`, `eips`, or `koreader` |
| `external_power` | Optional 0/1 only if separately detectable |
| `wifi_rssi_dbm` | Optional signal strength if cheaply available; no network scan |
| `frontlight_level` | Optional raw level; do not assume the same scale across models |
| `uptime_seconds`, `storage_free_kib`, `memory_available_kib` | Optional diagnostic telemetry; not necessary for routine rendering |
| `battery_temperature_c` | Optional verified battery sensor value; never label as ambient room temperature |
| `last_success_at`, `last_error` | Optional client status; time labeled as device-reported, error is a bounded code without logs or credentials |

Routine requests should contain only profile/page/geometry and available battery
state, with short compatibility fields when useful. Bound request size to 2 KiB.
Use URL encoding for free-text version strings; current shell sanitization is
not a general encoder. Numeric fields must reject NaN, infinity and out-of-range
values. A v1 implementation must define explicit bounds before accepting each
optional diagnostic field; the list above is not authorization for unvalidated
arbitrary telemetry.

No automatic transmission of serials, MAC addresses, SSIDs, account credentials,
reading history or full logs. Weather location is configured on the NAS rather
than inferred from the Kindle. Full hardware diagnostics stay a separate manual
operation. Telemetry is an observation at fetch time; an offline page's battery
value will age with the image.

Proposed additive endpoint (not implemented yet):

```http
GET /v1/dashboard.png?profile=home&page=markets-1&width=1236&height=1648&battery=73&charging=0&device=paperwhite
Authorization: Bearer <dashboard-token>
```

`/dashboard.png` retains its existing prototype behavior until deliberately
migrated. The `/v1/` prefix prevents new clients from mistaking a legacy generic
image for a requested market page. Unknown page/profile returns 404. Invalid
parameters return 422. V1 physical dimensions are rejected outside 320..2560,
rather than silently resized. Portfolio profiles must be authorized by token;
an arbitrary profile name is not permission to see someone else's holdings.

## NAS -> Kindle

Single-page success is HTTP 200, a full-size 8-bit grayscale PNG, no alpha or
interlacing, `Content-Type: image/png`, and `Cache-Control: no-store`. `no-store`
prevents ordinary HTTP intermediary caching; the app explicitly maintains its
own last-known-good offline artifacts.

Proposed response metadata:

```http
X-Dashboard-Contract: 1
X-Dashboard-Page: markets-1
X-Dashboard-Snapshot: <opaque-generation-id>
X-Dashboard-Generated-At: <UTC RFC3339 timestamp>
X-Dashboard-Data-State: fresh
```

Data state is one of `fresh`, `delayed`, `stale`, `partial`, or `unavailable`.
Source times and individual source states are also visibly rendered. A header
cannot replace visible freshness information because the Kindle may display
the cached image long after the HTTP transaction.

No server response can execute a client shell command, change power policy,
change URLs, or select an arbitrary filesystem path. Error bodies never replace
cached pages. Error responses expose no credentials or portfolio contents.

## Freshness, persistence and offline behavior

Every data record distinguishes:

- `source_as_of`: time the underlying quote/observation/account data represents.
- `fetched_at`: time the NAS last successfully fetched it.
- `generated_at`: time the NAS created the image.

All machine timestamps are UTC; rendered times include the configured local
timezone. Persist source timestamps with values. Re-rendering an old price does
not make it fresh, and a failed fetch must not advance the successful-fetch time.
Market closure is different from a stale live-session feed. Provider delay is
different from a connection failure. Weather forecast valid times differ from
its issuance time and should be labeled accordingly.

| Situation | Required result |
| --- | --- |
| Internet/provider unavailable, NAS reachable | Render last stored source values with original source times and stale/partial labels |
| One provider fails | Keep other sections useful; mark the failed section separately |
| NAS/Wi-Fi unreachable | Show the last validated local image/bundle unchanged; no repeated retry loop |
| No prior data for a section | Display unavailable/not configured, never synthetic live values |
| No local page on first use | Keep normal UI available and report the failure |
| NAS/container restarted without internet | Load persisted source snapshots; do not depend only on RAM caches |

The NAS needs a small persistent Docker volume for atomic JSON snapshots and
rendered artifacts. A database is unnecessary. This is a change from the current
original stateless placeholder renderer. The current implementation reads a
validated atomically published full snapshot from a read-only persistent volume;
upstream collectors are still pending. Separate market/weather caches from optional private
portfolio artifacts; do not log account data.

The Kindle stores an independently validated cache per profile/page/geometry,
bounded to configured pages and a previous snapshot. A multi-page bundle is
promoted atomically as one generation, with temporary metadata and files removed
after failure. Avoid accumulating a new retained snapshot on every refresh.

A static offline PNG cannot update a relative label such as "15 minutes ago"
while asleep, nor magically add an "offline" banner when the NAS becomes
unreachable. Always burn absolute source times into the image. During a LAN
failure those timestamps remain the reliable evidence of age. Any future live
overlay would be a separate client feature, not assumed by this contract.

## Carousel / page navigation

User decision: the dashboard is standalone. Do not use KOReader, a book document,
CBZ packaging, or another application's viewer for navigation. KOReader may be
studied as a reference for device behavior, never as a runtime dependency.

The shell MVP can add explicit Next/Previous KUAL actions selecting local cached
PNG pages. This requires returning to KUAL; a one-shot framebuffer draw has no
touchscreen event handler. These KUAL actions are now implemented, including wraparound.

The target experience is a small standalone session with next/previous touch
actions, full-screen cached PNG display, refresh and a reliable exit action.
Input handling must use a verified existing device capability or a separately
agreed implementation; raw binary input events cannot be assumed safely portable
across unknown Kindle models. No custom compiled binary is required by the MVP.

An eventual session process must block waiting for events, cooperate with normal
suspend, and release all owned resources on exit. It must not poll continuously,
generate synthetic activity, prevent sleep indefinitely, or draw over the native
lockscreen. Tap-to-wake from deep sleep is not assumed. Page changes remain fully
offline and never toggle Wi-Fi. Implementation is gated on device diagnostics.

## Power and Special Offers

An unchanged e-ink image does not imply that the CPU/radio are sleeping. Page
turning while awake, CPU idle, and deep suspend are separate operating states.
Do not promise touch wake from deep sleep; its availability is model-dependent.

Keep the original boundaries: no Special Offers patch, lockscreen replacement,
fake interaction heartbeat, indefinite suspend inhibitor, or guessed suspend
command. KOReader itself routes Special Offers sleep to the native screensaver.
Its event-driven input and device-specific handling are useful inspiration;
they do not establish an always-visible dashboard through sleep on this device.

The durable guarantee is preservation of local pages, useful offline navigation,
and a recoverable session. Continuous dashboard visibility together with deep
sleep and unchanged advertisement behavior is unresolved and may be incompatible.
If diagnostics show no supported path satisfying all boundaries, retain normal
sleep/ads and return to the cached dashboard after normal wake. Do not continually
redraw over an advertisement to simulate retention.

Manual refresh stays the default. Later policy candidates remain 60 minutes
normally, 4 hours overnight, reduced activity below 20% battery, no rapid retry,
Wi-Fi used only for an explicit fetch, and no timed carousel animation. Provider
collection may occur independently on the NAS without waking the Kindle. Exact
suspend/wake and radio operations require the original diagnostics first.

## TrueNAS integration

Candidate read-only tiles: NAS uptime/version, CPU load and memory, storage pool
health/capacity, active alert counts, disk temperatures when exposed, and selected
app/backup/scrub status when that release supplies it. Each value has a sample
time; NAS online must not mean every disk, pool or container is healthy.

The exact TrueNAS version is required. Current documentation describes a
versioned WebSocket JSON-RPC API and removal of legacy REST in version 26. That
conflicts with this project's original no-WebSockets constraint. No direct
TrueNAS API collector is approved or implemented by this document. With that
constraint retained, use an explicitly configured NAS-side metrics exporter or
file snapshot exposed through HTTP/local read-only storage; compatibility and
availability must be verified. A short-lived NAS-only API connection is another
option only if the user explicitly relaxes that constraint later. Kindle traffic
remains short HTTP requests in either case.

Use a dedicated least-privilege supported account for any future direct adapter.
No host root credentials, privileged container or Docker socket are needed by
the renderer. Do not make deployment depend on a particular TrueNAS Apps UI
until the installed release is known.

## Portfolio and research extensions

Portfolio v1 should be read-only: positions, quantities, account-reported values,
cash, allocation and gains only where cost basis and data definitions support
them. Hide account identifiers; choose whether absolute balances appear on an
exposed e-ink screen. Broker credentials remain on the NAS. Dashboard tokens must
never confer trading permission. Separate holdings-as-of and quote-as-of so
stale share counts are not presented as a live portfolio.

Practical initial input: user-exported holdings CSV. Next, evaluate a supported
authorized brokerage/aggregator integration for the user's accounts and region.
Robinhood's documented public API found during this review is for crypto; it is
not evidence of a supported equities portfolio API. Fidelity Access supports
authorized connections through integrated third parties; it does not establish
that a personal self-hosted app can obtain a direct API key. Do not promise
either connection before confirming access. No credential scraping is planned.

A research page may display indicators, watch conditions and explanations. Each
condition includes its rule/version, source prices, evaluation time and data
freshness. Call these research alerts, not guaranteed buying opportunities.
Disable current buy/sell-style alerts if inputs are stale or incomplete; historical
alerts may remain visible only as dated, expired observations. No automatic trade
execution or broker order endpoint is within this dashboard's scope.

## Decisions still needed

- Weather location, Fahrenheit/Celsius and display timezone.
- TrueNAS product/version and available metrics sources under the no-WebSockets boundary.
- Device-supported input handling for a standalone carousel; KOReader viewing is excluded.
- Market-data provider, available index coverage, permitted use and acceptable quote delay.
- Original Kindle diagnostics and observed sleep/wake behavior.

## Sources reviewed

- [KOReader Kindle device adapter](https://github.com/koreader/koreader/blob/master/frontend/device/kindle/device.lua): Special Offers screen-saver routing.
- [TrueNAS API reference](https://www.truenas.com/docs/scale/api/): version-dependent transport and authentication.
- [Robinhood Crypto API](https://robinhood.com/us/en/support/articles/crypto-api/): supported public crypto account/holdings access.
- [Fidelity Access](https://www.fidelity.com/security/fidelity-access-data-security): authorized integrated third-party data sharing.
