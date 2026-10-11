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
A useful small card shows remaining allowance, reset time and the latest reported
daily token count. Add the widget only if you enable this integration.

Available fields include primary/secondary allowance used or remaining, their
reset times, lifetime and peak daily tokens, latest reported day tokens, current
and longest streaks, and longest turn duration. Missing values display as unknown.
Window durations come from the account response: there is no assumed five-hour
window. Accounts may return only one window; absent secondary values stay unknown.

The source's sync time is always visible. Data becomes stale after two hours, or
when a reported quota reset passes without another reading. An expired window
shows **Awaiting sync**; it is never assumed to reset to zero usage. The daily token
label uses the provider's date, rather than silently calling it the NAS's “today.”
Token totals describe reported account activity, not message counts or an API bill.

## Container setup on a NAS

The optional `scripts/refresh-codex-usage-nas.sh` runner starts a short-lived
container containing Python 3 and a compatible signed-in Codex CLI. Configure
`USAGE_IMAGE`, `USAGE_AUTH_DIR`, `USAGE_UID`, `USAGE_GID`, `USAGE_READER_GID` and
`USAGE_OUTPUT_DIR` for your installation; its legacy defaults describe the tested
deployment and should not be assumed to exist on another NAS.

Only the reader mounts the Codex login directory. The web renderer receives the
filtered snapshot at `/data/codex/usage.json`, selected by `CODEX_USAGE_PATH`.
Create the output directory with suitable owner/group and setgid permissions;
for example, reader UID 568 with reader group 10001, directory mode 2750 and
snapshot mode 0640 allows renderer UID 10001 to read it.

The runner has an overlap lock and a 90-second limit. Its own container is cleaned
up on exit. Root filesystem is read-only, capabilities are dropped and no ports
are published. Codex has writable access to its existing login directory for
its own authentication refresh; no account credentials enter the renderer.
Failed collection retains the last working snapshot.

Schedule the runner every 30 minutes in TrueNAS Cron Jobs or ordinary cron.
The host job needs Docker access, while the reader process runs as the configured
non-root user. The Kindle picks up the result on its next refresh.

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
using your existing Codex login workflow. The dashboard does not initiate login
or replace credentials. Re-authentication stays with your existing setup.

To stop collection, disable **Kindle Dashboard Codex usage** in TrueNAS's Cron Jobs
settings. Removing the widget alone does not disable collection. Disabling the job
does not sign Codex out or affect other applications. The last reading will become stale normally.
