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

Refresh/page controls set the app interval, night interval, optional rotation and
comma-separated page order. Remove an ID from the order to hide that page from
navigation; its saved layout remains. Valid IDs: overview, weather, markets-1,
markets-2, nas. These preferences update on the next app fetch. Saving does not
wake the Kindle. Native sleep cannot be bypassed by a JavaScript timer.

Connection & source details show timestamps, NAS metrics and last Kindle contact.
A newly rendered image may contain older quotes: the footer reports older source
data. Source names and repetitive timestamps are omitted from the image itself.

ChatGPT usage has been removed. The service runs independently on the NAS.
