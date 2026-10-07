# Pages, previews and persistent input data

Five page IDs are implemented on the existing image endpoint: `overview`,
`weather`, `markets-1`, `markets-2`, `nas`. For example:

```text
GET /dashboard.png?page=markets-1&width=1236&height=1648&battery=73&charging=0
```

The response acknowledges `X-Dashboard-Page: markets-1`. The updated client
requires this header, so update the server and Kindle client together. This
avoids caching an old server's generic page under the wrong name. The proposed
`/v1/` contract is not yet exposed. Invalid page IDs return 422.

## Design

White background, large headings, generous margins, aligned quote columns,
grayscale weather panels and explicit signed changes replace the old placeholder
page. The editable overview uses a compact widget grid; detail pages retain
their page numbers. Every page has a generation timestamp and source times. All
freshness/status labels describe conditions at image generation. A cached PNG
cannot update those labels while offline; use its dates to judge age.

Preview files:

- [Overview](previews/overview.png)
- [Weather](previews/weather.png)
- [Markets 1](previews/markets-1.png)
- [Markets 2](previews/markets-2.png)
- [NAS](previews/nas.png)

All preview values are synthetic and prominently labeled SAMPLE DATA. Sample
San Francisco weather is not a chosen user location. The server never loads the
sample fixture unless explicitly configured to do so.

## Offline carousel

Run KUAL -> Dashboard -> Refresh All Pages to populate the cache. It makes at
most five sequential requests, retains older pages on failure and stops at the
first failed fetch. It then displays the selected page if available. A partly
successful batch can contain different source/image times, shown on each page.
It is not an atomic multi-page generation.

Next/Previous Dashboard (cached) wraps through local files only. It refuses a
missing page or wrong resolution and leaves the displayed page intact. One
image per page plus the current display image bounds storage; new resolutions
replace each page's prior cache. Refresh Dashboard refreshes only the currently
selected page. Direct taps on the dashboard itself are not implemented.

## Supply source data without fake live values

`server/app/snapshots.py` defines a validated JSON schema for weather, watchlist
quotes, NAS metrics and optional ChatGPT usage summaries. A complete example is
`docs/previews/sample-snapshot.json`. Records contain source name, timezone-aware
`as_of` and `valid_until`. Expired values remain visible as STALE with their
original source time. Future source timestamps render CHECK TIME. Quote basis is
validated: previous close for equities/index/ETFs, 24h for crypto.

The renderer reads `DASHBOARD_SNAPSHOT_PATH` each request with a 256 KiB limit.
Docker Compose mounts `server/data/` read-only at `/data` and reads
`/data/snapshot.json`. With no file, weather/quotes/host metrics are unavailable;
the NAS page reports only that the dashboard service responded. Invalid files
also fail closed to unavailable data without exposing contents in logs.

Publish a full validated snapshot on the NAS/development host:

```sh
# Install server requirements in the host venv first.
python scripts/publish-snapshot.py /path/to/incoming.json
```

It validates before replacing `server/data/snapshot.json` atomically. Invalid
input never replaces the prior file. A Docker restart or loss of internet does
not delete the persisted snapshot. Upstream collectors should retain a record's
original as_of on failure and publish complete merged snapshots; do not advance
timestamps just because the file is rewritten.

**Optional live adapters are implemented.** See [setup.md](setup.md) for
Open-Meteo weather, Finnhub or Twelve Data equities/index, Coinbase crypto, and the TrueNAS
host snapshot exporter. Location, keys/entitlements and host version still need
deployment configuration. The snapshot boundary keeps credentials and management
access off the Kindle. Do not manually publish into a file owned by the running
collector. No brokerage or portfolio data is accepted by the current schema.

The overview editor can select from the original 12 instruments plus AAPL, TSLA,
GOOGL, MSFT, NFLX, NVDA, ADBE, SCHD, SPY, DIA, QQQ, IWM, TLT, GLD and DBC.
`MARKET_SYMBOLS` controls which equities the collector fetches. The two detail
market pages retain the original screenshot watchlist. GOOG and GOOGL remain
distinct. Imported BTCUSDC/ETHUSDC entries identify the assets; the dashboard
continues to display Coinbase BTC-USD/ETH-USD quotes, not Binance USDC prices.

To regenerate the design examples only:

```sh
python scripts/generate-example.py
```
