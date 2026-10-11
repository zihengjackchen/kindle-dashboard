# Requested features: status on 2026-10-11

| Request | Status |
| --- | --- |
| Native document and KUAL launch, top X exit | Implemented; device reopened and fresh bundle verified |
| Previous/Refresh/Next at top, no permanent status row | Implemented |
| Informative opening state and temporary refresh status | Implemented inside the native app; no framebuffer startup text |
| All pages downloaded together, offline cached navigation | Implemented; one NAS bundle request |
| Weather for 98122, C and F | Implemented |
| Stocks, crypto and existing 22-symbol watchlist | Implemented; older market data remains labeled |
| NAS metrics, Backblaze job details, Kindle telemetry | Implemented, selectable fields; missing values remain unknown |
| Dense multiple-column layouts, accurate app aspect ratio | Implemented |
| Widget drag/reorder, sizes, field selection, live preview | Implemented |
| Multiple instances of each widget, individual content | Implemented; up to twelve per page |
| Explicit row/column placement | Implemented; overlapping cells rejected |
| Markdown widget with shrink/truncate behavior | Implemented; bounded subset, no remote assets or HTML rendering |
| Page ordering, optional rotation, refresh/night intervals | Implemented while app is awake |
| Reduced polling / no frequent browser heartbeat | Implemented; native events with a 30-minute fallback audit |
| Frontlight zero on entry and restoration on exit | Implemented; true LED-off is not verified on this older model |
| Continuous foreground display on battery or USB | Enabled on the installed device; owned native sleep hold and X exit tested. Overnight endurance remains unmeasured |
| Unplugged low-battery behavior | Foreground refresh slows below 20%; native sleep remains in charge |
| Automatic suspend and scheduled hardware wake | Production refresh loop not enabled. Guarded [one-cycle native alarm test](native-sleep.md) implemented; physical alarm wake still unverified |
| Portfolio integration with Robinhood/Fidelity | Future; no account connection or provider contract configured |
| Stock analysis / buying signals | Future; no strategy or analysis provider specified |
| ChatGPT usage | Removed as requested |
| GitHub publication | No remote configured in this repository; local commits and source bundle available |

The editor does not change device power settings or expose NAS privileged controls.
Special Offers, the native lockscreen and boot configuration remain untouched.
