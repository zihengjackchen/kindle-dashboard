# PNG service

The current editor supports all five pages, drag-and-drop widget ordering, field selection, refresh settings and rendered previews. The TrueNAS host exporter includes B2 Cloud Sync summaries and bounded system metrics. ChatGPT usage is removed. See [Kindle app](../docs/kindle-app.md).

Routes are `GET /health`, `GET /dashboard.png`, authenticated `GET /status`,
`GET /dashboard-bundle.json`, `GET /client-config.json`, `GET /layout`, `PUT /layout`, `POST /preview.png`, and the dashboard studio at `GET /`.
See [the editor guide](../docs/dashboard-editor.md) for layout controls and API details.
The service has no database, system control endpoints,
or Docker socket. An optional separate NAS collector performs provider calls;
the image request path never does.
Health returns `{"status":"ok"}` without authentication. The image endpoint uses
an optional shared bearer token and returns `image/png` with `Cache-Control:
no-store`. Errors return JSON and must never enter the Kindle image cache.

## All-page app refresh

`GET /dashboard-bundle.json` accepts the same dimensions, telemetry and bearer
header as `/dashboard.png`. It returns `application/json`, `Cache-Control: no-store`:
`version: 1`, `width`, `height`, `generated_at`, `battery`, `charging`, `settings`
(page names/order and refresh intervals), and `images` (page ID to base64 PNG).
All pages in the configured page order use the same snapshot, layout and timestamp.
Any rendering failure rejects the entire request. Responses are limited to 8 MiB.
The Kindle validates and decodes every image before committing the bundle cache.
The older single-PNG endpoint remains available for framebuffer refresh and previews.

## Docker deployment

```sh
cp .env.example .env
# Set API_TOKEN, DASHBOARD_TIMEZONE, and BIND_ADDRESS as needed.
docker compose up -d --build
docker compose logs --tail=50 dashboard
curl http://127.0.0.1:8080/health
```

Use a LAN IP reachable by the Kindle; `BIND_ADDRESS` defaults to all host
interfaces. Limit host firewall access to your LAN. Set the same `API_TOKEN`
in the Kindle's `config.sh`; leave both blank only for an unauthenticated trusted
LAN setup. A reverse proxy must serve the image directly without redirects.

```sh
curl --fail --output dashboard.png \
  --header 'Authorization: Bearer your-shared-token' \
  'http://192.168.1.20:8080/dashboard.png?battery=73&charging=0&width=1236&height=1648&device=paperwhite'
```

Omit the Authorization header if authentication is disabled. The container runs
as an unprivileged user on a read-only filesystem, with bounded concurrency,
memory, and Docker logs. Fonts are supplied by Debian's `fonts-dejavu-core` package,
whose license is included by Debian under `/usr/share/doc/fonts-dejavu-core/`.
Pillow's bundled scalable font is the local-development fallback. Set
`DASHBOARD_FONT_PATH` for a custom local font if desired. No download happens
during rendering. The included example may use the local fallback font.

`DASHBOARD_TIMEZONE` is an IANA name such as `America/Los_Angeles`, default `UTC`.
Invalid zones fail startup. Time is the NAS clock at generation, not a live clock
on the Kindle. Ensure the NAS clock is synchronized normally.

## Request contract

| Parameter | Default | Validation |
| --- | --- | --- |
| `page` | overview | overview, weather, markets-1, markets-2, nas |
| `width` | 1236 | Integer 1..100000 accepted, clamped to 320..2560 |
| `height` | 1648 | Same; maximum image is 2560 × 2560 |
| `battery` | unknown | Integer 0..100; outside range returns 422 |
| `charging` | unknown | 0/1 or standard boolean strings, including true/false |
| `device` | unknown | 1..80 ASCII letters, digits, dots, underscores, hyphens |
| `device_id` | absent | User label, max 80 ASCII letters/digits/dot/underscore/hyphen; omission means no contact record |
| `rssi` | absent | -127..-1 dBm |
| `fetch_seconds` | absent | Prior validated download duration, 0..86400 |
| `fetch_failures` | absent | Prior consecutive failures, 0..999999 |
| `last_success_epoch` | absent | Prior validated download time, 0..4102444800 |

Missing query parameters produce a usable generic page. Zero, negative,
non-integer, and extreme dimensions (>100000) return 422. Positive dimensions
within the input bounds are clamped independently. The Kindle refuses to request
out-of-range screen sizes so its accepted image always matches actual configured
dimensions. Arbitrary orientation is supported; extreme aspect ratios prioritize
fitting the content over the optimal Kindle portrait layout.

Invalid tokens return 401. Rendering failures produce a logged exception and a
generic 500 response without exposing internals to the client. Access logging is
disabled in Docker to avoid accumulating telemetry URLs; application failure
logging remains enabled. The renderer uses 8-bit grayscale, no alpha/interlacing.

The server acknowledges the requested page with `X-Dashboard-Page`. Updated
clients require it. Compose mounts `data/` read-only for an optional persisted,
validated weather/quotes/NAS snapshot. See [pages and data](../docs/pages-and-data.md)
for publishing and the source schema. Optional live adapters and their setup are
documented in [setup](../docs/setup.md); absent data renders unavailable, never
synthetic design fixtures. Compose mounts a separate writable contact-state
volume, owned by UID 10001. Only the collector needs write access to `data/`.
The same state volume holds `DASHBOARD_LAYOUT_PATH=/state/layout.json` for saved
overview preferences. A nonempty `API_TOKEN` is required to use the editor.

## Local development and checks

From repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r server/requirements-dev.txt
python -m pytest -q
python scripts/generate-example.py
uvicorn app.main:app --app-dir server --host 127.0.0.1 --port 8080
```

Run server-only tests with `python -m pytest server/tests -q`. See the root README
for shell integration tests and manual client simulation. This environment may
not have a Docker daemon; verify container deployment on the NAS with
`docker compose ps` and the example request before Kindle testing.
