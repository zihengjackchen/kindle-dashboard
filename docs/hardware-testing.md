# Hardware acceptance and power gate

Host tests validate logic, HTTP handling, and PNG generation. They cannot certify
your Kindle's KUAL timing, display driver, firmware behavior, or power use.

## Manual acceptance

1. Run diagnostics and confirm model, firmware, geometry and available commands.
2. Deploy Docker; obtain `/health` and a PNG from another LAN machine.
3. Configure URL/token, physical dimensions if needed, and backend path. Enable
   Wi-Fi through the normal UI. Leave both automation flags at 0.
4. Select Refresh Dashboard. Confirm an edge-to-edge grayscale image, readable
   text and a visible full refresh. Confirm battery/charging match the device.
   Record whether KUAL/framework repaint overwrites the image and after how long.
5. Refresh a second time. Check `logs/dashboard.log` for successful HTTP 200,
   validation, backend and display. Confirm there is no remaining dashboard task.
6. Temporarily stop the NAS service. Refresh should fail once, retain/repaint the
   old cache, and keep its original generated timestamp. Restart the NAS.
7. Start Dashboard; verify `state/active`. Stop Dashboard; verify it is removed,
   KUAL reloads, and normal Home/book navigation works.
8. Create the USB kill switch. Verify start/refresh refuse to draw and stop still
   works. Remove it after testing.
9. Use the normal power button once. Record normal sleep/wake behavior without
   changing Special Offers. Seeing the Amazon ad screen is expected and allowed.
10. Populate the five caches with Refresh All Pages, disconnect Wi-Fi normally,
    and test KUAL Next/Previous including wraparound. Tapping the image itself
    does not yet navigate.
11. Only after the read-only profile review in [native-wake.md](native-wake.md),
    test automatic cached redraw after actual lockscreen exit. Confirm no network
    request, no drawing over the ad screen, and that Stop ends the listener.

If a step fails, retain diagnostics and the concise logs. Do not compensate by
stopping the framework, blocking the screensaver, or disabling powerd.

## Milestone 5 admission criteria

No suspend command or scheduler is included. A blocking native event listener
is included but disabled until its model/firmware/lockscreen guard is verified.
A later scheduled-wake implementation needs:

- Exact model/SoC/firmware and documented, observable power transitions.
- A verified supported wake source and a reliable exit/recovery route.
- Evidence that any image retention does not modify or bypass the ad lockscreen.
- Radio state capture/restoration and bounded connection attempts.
- Measured idle and refresh energy use, including frontlight and network cost.
- Tests for network failures, depleted battery, night periods, and missed wakes.

Only then decide whether optional 60-minute refresh, 4-hour night refresh, and
reduced frequency below 20% battery are appropriate. If no safe retention path
exists while Special Offers remain active, keep this as a manual dashboard.
