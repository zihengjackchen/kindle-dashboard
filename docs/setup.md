# Install Daylight

> Library app update: see [Kindle app](kindle-app.md) and [editor](dashboard-editor.md). The manual KUAL workflow below remains a fallback; its restrictions do not describe the new app timers and touch controls.

## Prepare a matching Kindle and NAS configuration

Use Python 3.13 with the project's requirements installed. From the repository root:

```sh
python scripts/setup.py --nas-url http://192.168.1.20:8080 \
  --timezone America/Los_Angeles --device-id bedside
```

Optionally add `--latitude 47.61 --longitude -122.33 --location Seattle --unit F`;
these coordinates are an example, not a default. The command creates:

- `server/.env`, including a newly generated bearer token.
- `dist/private/kindle-dashboard-configured.zip`, with the matching endpoint/token.

Both are private and ignored by Git. Do not attach the configured ZIP to a release.
The setup script refuses to overwrite an existing `.env`. To change an existing
installation, edit `.env` and the Kindle's `config.local.sh` with matching tokens.
`config.local.sh` overrides `config.sh` and is excluded from default release packages.
No private GitHub, market, or brokerage credentials belong on the Kindle.

## Start the NAS service

On a Docker host:

```sh
cd server
docker compose up -d --build
```

Visit `http://NAS_IP:8080/` for the preview and connection check. Enter the dashboard
token from `.env`; it is used only in request headers and kept in tab memory.
This UI has no polling, configuration-writing, power-control or trading endpoints.
`/health` is public; `/dashboard.png` and `/status` require the configured token.
Use a trusted LAN or appropriately configured HTTPS; plain HTTP does not encrypt tokens.

To enable NAS-side data collection, edit `.env` and grant container UID 10001 write
access to **this project's data directory only**. On ordinary Linux, from `server`:

```sh
sudo chown 10001:10001 ./data
docker compose --profile live up -d --build
```

For TrueNAS datasets, use the dataset permissions UI to grant UID 10001 the required
access instead. The rendering container sees data read-only. Only the collector
writes snapshots; it never receives the Docker socket or TrueNAS management socket.
Keep one collector per snapshot file. Do not concurrently run the manual snapshot
publisher against a collector-owned file.

Live collection runs on the NAS once an hour (configurable, minimum 15 minutes).
It does **not** schedule Kindle wakeups or refresh its screen. Restart the collector
after changing configuration. Market calls are spaced eight seconds apart and a
ten-instrument collection takes over a minute; individual failures retain old data.
Both services have Docker health checks. The collector check confirms recent
snapshot publication, not upstream freshness; `/status` exposes source timestamps.
For a deployment that waits for readiness, use
`docker compose --profile live up -d --build --wait --wait-timeout 300`.

## Configure live sources

| Source | Configuration | Behavior |
| --- | --- | --- |
| Weather | `WEATHER_LATITUDE`, `WEATHER_LONGITUDE`, `WEATHER_LOCATION`, `WEATHER_UNIT` | Open-Meteo current conditions and three following days; no key for its public noncommercial service |
| Equities/ETFs/index | `TWELVE_DATA_API_KEY` | Exact watchlist; account plan, quota and instrument entitlements apply |
| Finnhub equities/ETFs | `FINNHUB_API_KEY`, optional `MARKET_SYMBOLS` | Preferred when this key is set; header authentication and two-second request spacing. Session is unknown because the quote endpoint does not report it. |
| S&P 500 | `TWELVE_DATA_SP500_SYMBOL=SPX` | Verify the provider's index symbol and your entitlement; never silently substitute an ETF |
| Market delay label | `MARKET_DATA_DELAYED=1` | Conservative default; change only when your account's data entitlement supports it |
| BTC/ETH | `CRYPTO_ENABLED=1` | Coinbase public USD product statistics, rolling 24-hour change; timestamp explicitly means observed at |
| TrueNAS | `NAS_SNAPSHOT_PATH=/data/nas.json` | Reads the limited host export described below |

Weather and quote source timestamps are retained when a fetch fails. Missing data
stays unavailable; synthetic prices are never used outside the labeled previews.
Quotes older than two hours are conservatively stale, including weekends/closed
markets. Closed-market status and delayed data are shown separately. NAS exports
expire after 30 minutes. The default hourly collector can therefore show stale NAS
data; lower its interval to 900 seconds when using a 15-minute NAS export.
Provider access is a deployment prerequisite, not included with this repository.

Provider references: [Open-Meteo](https://open-meteo.com/en/docs),
[Finnhub quote API](https://finnhub.io/docs/api/quote),
[Twelve Data](https://twelvedata.com/docs),
[Coinbase product statistics](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-stats).
Review the provider's applicable usage and display terms for your deployment.

## TrueNAS SCALE

First confirm the installed SCALE version. SCALE 24.10+ uses Docker-based Apps;
older Kubernetes-based installations need different deployment steps. See the
[official Custom App instructions](https://www.truenas.com/docs/scale/apps/installcustomappscreens/).

Either use the ordinary Compose checkout on your Docker server, or use
`server/truenas-compose.yml` in **Apps / Custom App / Install via YAML**. Replace
`YOUR_OWNER`, `YOUR_TOKEN`, and `POOL`, and fill the desired source settings before
submitting. Create the dataset/directory first and grant UID 10001 write access.
Use the actual published image URL from the GitHub Actions run. For a private
GHCR package, configure the registry credentials in TrueNAS or build locally;
repository visibility alone does not guarantee anonymous container pulls.

For actual host health, copy `scripts/export-truenas.py` to your application
dataset and run it on the **TrueNAS host**, not inside the dashboard container:

```sh
python3 /mnt/POOL/apps/kindle-dashboard/export-truenas.py \
  --pool POOL --output /mnt/POOL/apps/kindle-dashboard/data/nas.json
```

It makes three read-only local `midclt` calls: `system.info`, `pool.query`, and
`alert.list`; reads Linux CPU/memory counters; and atomically writes a filtered
snapshot. Raw system info, serial numbers and alert text are not exported.
Run with a host account authorized to read those methods. After verifying one
export, optionally schedule this exact command every 15 minutes using TrueNAS
Tasks. Nothing in the app installs a host task automatically.
The parser targets the documented 25.10 response fields and must be verified on
your installed version. Failures leave the prior export intact; an unavailable
pool capacity does not conceal a reported unhealthy pool status.

## Install on Kindle

1. Extract the configured ZIP to the Kindle USB root. It creates
   `extensions/dashboard/` with the KUAL manifest and scripts.
2. Safely eject USB; open KUAL, then **Dashboard / Show Diagnostics**.
3. Configure a verified screen size/backend if detection fails. Enable Wi-Fi
   normally in Kindle Settings.
4. Select **Refresh All Pages**, then use **Next/Previous Dashboard (cached)**.
5. Select **Start Dashboard** for an active session. Native sleep and Special
   Offers remain in control. Automatic cached restoration requires the verified
   profile in [native-wake.md](native-wake.md); it is disabled by default.
6. Select **Stop Dashboard** to end the session. The recovery kill switch is an
   empty `dashboard-disable` file at the USB root; see [recovery.md](recovery.md).

This is a KUAL carousel. Direct touchscreen page-turn handling and automatic wake
scheduling are not included. Neither is needed to use cached pages through KUAL.

## Updates and backup

Keep a copy of `config.local.sh`, `server/.env`, source snapshots, and the contact
state volume. Stop the Kindle dashboard before copying a new public ZIP over its
extension. A public ZIP contains no `config.local.sh`, so your private settings
remain separate; do not delete the existing extension folder during an update.
For NAS source builds, pull and run `docker compose up -d --build` again. For a
published image, prefer the immutable `sha-<commit>` tag after validating an update.
No Kindle boot files, lockscreen files, or framework services are modified.
