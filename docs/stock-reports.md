# Paginated stock updates

Updated clients can now render the original Markdown locally, with A−/A+ text
controls and no report images in their bundle. See [local Markdown](local-markdown.md).
The PNG path described below remains available for older clients and NAS previews.

The stock-update pages display the original Markdown `content` from the NAS
Discord publisher's dated digest archive. Dashboard does not generate another
summary, call a model, contact Discord, or execute the report's trading ideas.
The report's dates, qualifications and original headings remain visible.

In the web editor, enable **Stock update report**, choose a text size, and use
**Preview report** with its Previous/Next controls. Save, then Refresh on Kindle.
Report pages follow the normal dashboards. All pages arrive in the same bundle;
Kindle Previous/Next needs no network request. The renderer uses the app's actual
image viewport, excluding native controls. It adds only a source-date/page footer.

Unlike a small Markdown widget, a report does not shrink or truncate to fit.
Paragraphs continue onto subsequent pages. Bold, italic, headings, list bullets,
quotes, fenced/inline code and link labels are rendered; links and images are
never fetched. The container includes DejaVu and Noto CJK fonts. Raw HTML is
inert text. PNG pages are not clickable documents.

## Connect the existing publisher

The dashboard container reads a directory of `YYYY-MM-DD.json` files with only:

```json
{"local_date":"2026-11-02","created_at":"2026-11-02T16:33:00+00:00","content":"Original Markdown here"}
```

For the existing TrueNAS setup, extend the existing NAS-health cron command:

```sh
/usr/bin/python3 /PATH/kindle-dashboard/scripts/export-truenas.py \
  --pool YOUR_POOL --output /PATH/kindle-dashboard/server/data/nas.json \
  --report-source /PATH/publisher/notifications/DESTINATION/combined-digests \
  --report-output /PATH/kindle-dashboard/server/data/reports
```

Run this as the existing host-export user with access to the private archive.
`export_stock_report.py` must sit beside `export-truenas.py`. The exporter copies
only the three fields above, preserving the exact Markdown. Source snapshots,
attachments and delivery receipts stay private. Exports use atomic replacement,
directory mode 0750 and file mode 0640, owned by the container UID/GID 10001.
The publisher archive and its permissions are unchanged.

Set `DASHBOARD_REPORT_DIRECTORY=/data/reports` in `server/.env` and recreate only
the dashboard service with `docker compose up -d --no-deps dashboard`. `/data`
already mounts read-only. The existing 15-minute host export updates the digest;
the Kindle receives it on its next configured refresh. No new Kindle timer runs.

The newest valid dated export wins. Invalid/missing exports retain the previous
in-memory report or an older valid disk export. A first installation without a
report displays an unavailable message. Source dates are never replaced with
the fetch time. If a fetch fails, Kindle retains the entire last decoded bundle.

## Limits and recovery

Reports are bounded to 40,000 characters, 27 report pages, and the existing 8 MiB
bundle limit (32 total pages including five dashboards). Exceeding a limit fails
the refresh and retains the old bundle; it does not cut off the report. The
exporter accepts publisher archives up to 32 MiB but exports no large snapshots.

Disable the report checkbox to return to dashboard-only bundles. Keep the old
container image, layout JSON and client files when upgrading. Server and client
must both support report page IDs; older clients reject the expanded bundle
safely and retain their cached images.
