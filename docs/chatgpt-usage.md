# ChatGPT usage snapshot

The dashboard can show lifetime tokens, peak daily tokens, current usage streak,
and a reported account-limit window with its reset time. These are usage metrics,
not an API spending bill or a count of all ChatGPT messages.

The exporter uses the documented `account/usage/read` and `account/rateLimits/read`
methods from [Codex App Server](https://learn.chatgpt.com/docs/app-server). It starts
a short-lived local process using the PC's existing Codex sign-in. It does not
start an agent turn, make an inference request, scrape the settings page, export
cookies, or copy login credentials to the NAS. Only explicitly selected numeric
metrics, timestamps and a fixed limit label are published. Account IDs, thread
details and provider credential fields are discarded.

On the signed-in Windows PC, from the repository directory:

```powershell
.\.venv\Scripts\python.exe scripts/export-chatgpt.py --nas truenas_admin@192.168.1.8
```

The script writes `dist/private/chatgpt.json` locally and atomically publishes
`/mnt/Main/kindle-dashboard/server/data/chatgpt.json` over existing SSH access.
Use `--codex PATH` if Codex is not on PATH, or `--nas-directory /mnt/POOL/.../data`
for a different deployment. It needs the existing NAS account's authorized sudo
access to publish a file owned by the container's UID 10001. No SSH credentials
are saved in source or transferred to Docker.

Compose points the collector at `/data/chatgpt.json`. The next collector cycle
imports it (within 15 minutes in the current deployment), preserving the source
time. Add the **ChatGPT usage** widget in the web editor, save, then refresh the
Kindle overview. The web editor also links directly to
[ChatGPT usage settings](https://chatgpt.com/settings/usage?tab=overview).

**PC synchronization is manual in this release.** The NAS cannot independently
refresh a sign-in held on the PC. The snapshot becomes STALE after two hours;
old values remain visible with their original time. The Kindle does not wake to
refresh it. You may separately schedule the same one-shot command on an always-on
signed-in PC; no Windows task or Kindle startup automation is installed here.

If sign-in expires, Codex is unavailable, or the provider changes the interface,
the command exits with an error and leaves the existing snapshots intact.
Missing metrics remain unknown. Reported limit IDs can cover a particular
product; the widget says **Codex** when that is the returned limit ID rather than
claiming it is a universal limit for every ChatGPT feature.
