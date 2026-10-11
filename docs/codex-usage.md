# Codex / ChatGPT usage on the NAS

The usage widget reads the existing NAS Codex login. It has no dependency on the
Windows PC, a browser session, or an active assistant conversation.

Every 30 minutes a TrueNAS cron job starts a short-lived container, reads two
documented Codex app-server methods, writes a filtered JSON snapshot atomically,
and exits. The dashboard reads that snapshot when rendering the normal page bundle.
There are no model inference requests or additional Kindle network calls.

## Display and customization

In the web editor, add **Codex / ChatGPT usage**. It supports the same placement,
width, height, custom title, duplication and field selection as other widgets.
The installed overview includes a full-width small card with remaining allowance,
reset time and the latest reported daily token count. Other cards were preserved.

Available fields include primary/secondary allowance used or remaining, their
reset times, lifetime and peak daily tokens, latest reported day tokens, current
and longest streaks, and longest turn duration. Missing values display as unknown.
Window durations come from the account response: there is no assumed five-hour
window. The current NAS account reports one seven-day window and no secondary one.

The source's sync time is always visible. Data becomes stale after two hours, or
when a reported quota reset passes without another reading. An expired window
shows **Awaiting sync**; it is never assumed to reset to zero usage. The daily token
label uses the provider's date, rather than silently calling it the NAS's “today.”
Token totals describe reported account activity, not message counts or an API bill.

## Installed NAS setup

- Job: **Kindle Dashboard Codex usage**, every 30 minutes (TrueNAS cron job ID 2).
- Runner: `/mnt/Main/kindle-dashboard/scripts/refresh-codex-usage-nas.sh`.
- Reader: `scripts/export-codex-usage.py`, Python standard library only.
- Image: `kindle-dashboard-codex:0.162.1`, an additional tag of the existing TGP
  image. Tagging reuses its layers and leaves the TGP image and configuration alone.
- Existing login: `/mnt/Main/tgp/secrets/codex`, mounted at `/codex` for Codex's own
  authentication/refresh handling. No credential files are read by the exporter.
- Output: `/mnt/Main/kindle-dashboard/server/data/codex/usage.json`.
- Web service setting: `CODEX_USAGE_PATH=/data/codex/usage.json`.

Only the reader container mounts the login. The web renderer's existing data
mount contains the allowlisted summary, never authentication files. The reader
runs as UID/GID 568 with supplementary group 10001. Its output directory is owned
by 568:10001, mode 2750, and snapshot files are 0640. The renderer runs as UID 10001.
The host cron task uses root to invoke Docker; Codex itself does not run as root.

The runner has an overlap lock and a 90-second limit. Its own container is cleaned
up on exit; it never terminates another Codex process. Root filesystem is read-only,
capabilities are dropped, no ports are published, and research data is not mounted.
Codex has writable access to its existing login directory to handle token refresh.
If the read or publication fails, the last working snapshot is retained.

To refresh immediately on this NAS:

```sh
sudo sh /mnt/Main/kindle-dashboard/scripts/refresh-codex-usage-nas.sh
```

The updated reading appears on the Kindle's next automatic or manual Refresh.
No Kindle reinstall is needed. Restarting or sleeping the PC has no effect.

## Other Linux installations

With Codex installed and signed in under the desired Linux user:

```sh
python3 scripts/export-codex-usage.py \
  --codex /absolute/path/to/codex \
  --output /path/readable/by/dashboard/usage.json
```

Run that command as the signed-in user. Do not copy authentication into the web
container. Set `CODEX_USAGE_PATH` to the snapshot's container path and schedule the
reader at the desired interval. For the container runner, `USAGE_IMAGE`,
`USAGE_AUTH_DIR`, `USAGE_UID`, `USAGE_GID`, `USAGE_READER_GID` and `USAGE_OUTPUT_DIR`
can adapt the installed profile. Pre-create the output directory with suitable
owner/group and setgid permissions; the runner does not modify login permissions.

## Protocol, privacy and failure handling

The reader initializes Codex app-server over local stdio, then calls
`account/rateLimits/read` and `account/usage/read`. It makes no thread, turn, login,
logout, reset-credit or email requests. See the official
[Codex app-server account documentation](https://learn.chatgpt.com/docs/app-server#authentication-endpoints).
The usage endpoint requires a supported signed-in account; an API-key-only login
does not provide this account usage information.

Provider replies are filtered to numeric summaries, dates and a fixed quota label.
Account identifiers, thread details, provider free text, cookies and tokens are
never stored in the dashboard snapshot or sent to the Kindle. Raw errors/stdout
from Codex are not logged. The source file is limited to 16 KiB and validated again
by the server. Its health is visible in the editor's source badges and `/status`.

If the card becomes stale, run the runner and check the NAS Codex login/version
through the existing TGP login workflow. The dashboard does not initiate login or
replace the other workstream's credentials. Re-authentication, if necessary, stays
with that existing workflow.

To stop collection, disable **Kindle Dashboard Codex usage** in TrueNAS's Cron Jobs
settings. Removing the widget alone does not disable collection. Disabling the job
does not sign Codex out or affect TGP. The last reading will become stale normally.
