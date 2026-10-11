# Dashboard editor

Open the NAS URL and connect with your dashboard bearer token. The token stays
in the tab; exported layouts contain preferences, not credentials.

Choose a page. Each of the five pages has its own name, widgets, field settings,
watchlist, notes and spacing. The name appears in app navigation, not as a large
heading in the dashboard image.

Drag widget cards to reorder them. Adjacent half-width cards share a row; a lone
half-width card fills its row. Width and height controls determine grid size.
Arrow controls provide a keyboard/touch alternative. Expand **Fields to show** to
select individual readings. The rendered PNG preview updates after a short pause,
using the same renderer and dimensions as the Kindle. Save applies the complete
layout; Discard restores the last save. Reset and imports remain drafts until saved.

Use a full-width, large watchlist and three columns for the 22-instrument list.
The overview is intended for essential information. Use the server page and larger
widgets for extensive NAS diagnostics; choosing every field in a small widget will
reduce readability. Missing metrics display a dash, never an invented zero.

Refresh/page controls set the app interval, night interval and optional rotation.
The page list has enable checkboxes and drag/arrow ordering. Disabling a page hides
it from navigation without deleting its saved arrangement. The last enabled page
cannot be unchecked. These preferences update on the next app fetch. Saving does not
wake the Kindle. Native sleep cannot be bypassed by a JavaScript timer.

Connection & source details show timestamps, NAS metrics and last Kindle contact.
A newly rendered image may contain older quotes: the footer reports older source
data. Source names and repetitive timestamps are omitted from the image itself.

ChatGPT usage has been removed. The service runs independently on the NAS.

The preview starts at the native app canvas, 1056 × 1162 on the tested Paperwhite,
and uses the latest reported dimensions when a device is available. This excludes
Amazon's top bar and the app's navigation controls. **Actual pixels** lets you inspect
text at its rendered size; **Fit preview** restores the full-page view. On desktop,
the controls scroll independently so the preview and Save button remain accessible.

**Reset this page** restores its widget arrangement, spacing and watchlist column
count while preserving its symbols, notes, title, other pages and refresh settings.
It stays a draft until saved. Watchlist and notes controls appear only when their
widgets are present. Field labels and selected counts make the long NAS options
easier to scan; connection badges summarize source freshness separately from the PNG.

Weather's default page now includes a large dual-unit reading, forecast tiles with
highs and lows, and small Kindle/server cards. The server page groups storage, CPU,
memory, network, apps and scrub readings above backup and Kindle details. Explicitly
saved page overrides are retained. All pages keep one generated timestamp and a
warning when their source data is older or unavailable; a fresh image is not a promise
of fresh market quotes. Missing metrics remain dashes.

## Widget instances and placement

Add up to twelve widgets per page, including multiple widgets of the same type.
Each instance has its own key, fields, title and options. Use **Duplicate** under
**Placement & content** to start from an existing widget. Watchlist widgets can
select independent symbols and columns; weather cards can override units; notes
can override page notes; backup cards can select individual reported jobs.
Blank overrides inherit page settings. NAS field tooltips show reported values.

Choose **Row** and **Column** to reserve cells in the two-column grid. Full-width
cards occupy both cells. Overlaps are rejected. Auto cards fill remaining cells.
Row height follows its largest widget. Dragging or arrows returns the page to
automatic placement. Exported files retain all per-widget preferences.

## Markdown

Choose **Add a widget > Markdown**. Enter up to 4,000 characters and an optional
title. Supported: headings (# through ###), bold, bulleted/numbered lists, quotes,
inline/fenced code and link labels. HTML stays literal text; images become alt
labels; no URL or file is fetched. This is not a complete CommonMark browser.

**Shrink, then truncate** reduces text to a readable minimum, then adds an ellipsis
when it still cannot fit. **Keep text size, truncate** preserves the text size.
All drawing is clipped to the card. Increase height or width for more content.
The preview shows the final fit. Layouts/imports are limited to 64 KiB.

Kindle fields include external power, idle sleep hold and configured power policy.
These are observations from the last fetch, not live controls. A sleep hold may
belong to another app such as the SSH launcher. The editor does not enable
unverified suspend/wake or remotely change the device's power policy.
