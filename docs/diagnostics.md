# Milestone 1: collect device evidence

Copy `kindle-client/extensions/dashboard` to `/mnt/us/extensions/dashboard` over
USB (the USB root corresponds to `/mnt/us`). Keep `config.xml` and `menu.json`
together. Safely eject USB, open KUAL, then Dashboard -> Show Diagnostics (save
report). The menu stays open; the entry saves a report rather than launching a
text viewer or taking over the screen. If the menu has not reloaded, reopen KUAL.

Alternatively, from an existing SSH/terminal session:

```sh
sh /mnt/us/extensions/dashboard/diagnostics.sh
```

Reconnect USB and retrieve `extensions/dashboard/logs/diagnostics.txt`. The
report is capped at 64 KiB and replaced each run. It includes CPU/kernel/firmware,
memory/storage, available commands, framebuffer information, battery attributes,
and read-only power properties. No token or dashboard configuration is dumped.
CPU information may contain a serial number; redact that and identifying network
or storage details before sharing. Unknowns and missing commands are expected.

Send back:

1. The report, especially normalized detection, framebuffer, battery, and power
   sections. If it ends mid-section, report that it was truncated.
2. Kindle model/generation and firmware from Settings -> Device Info (omit serial).
3. Whether FBInk was installed separately or bundled, and its path if not on PATH.
4. KUAL version/type, and whether exiting KUAL returns to Home or an open book.
5. Whether the normal power button displays Special Offers, and whether waking
   returns to the prior page. Do not change advertisement settings to test this.
6. After manual refresh testing: whether the PNG fills the screen, whether it is
   overwritten immediately, and whether Stop Dashboard returns to KUAL cleanly.

Do not run suspend experiments, stop the framework, or change powerd properties.
The report is the input to a later model-specific power review, not evidence that
an advertised capability is safe to use.

For the implemented native-wake listener, also follow the read-only capture in
[native-wake.md](native-wake.md). `logs/wake-events.txt` records the native event
order. Automatic restoration remains disabled until a model/firmware-matched
lockscreen-exit guard has been confirmed.
