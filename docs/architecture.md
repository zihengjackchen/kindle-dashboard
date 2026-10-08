# Architecture and scope

> Library app update: see [Kindle app](kindle-app.md) and [editor](dashboard-editor.md). The manual KUAL workflow below remains a fallback; its restrictions do not describe the new app timers and touch controls.

This describes the implemented shell-client MVP. See the
[v1 roadmap](product-contract-v1.md) for longer-term requirements. Five pages,
source collectors, persistent snapshots, contact telemetry and a KUAL carousel
are implemented. KOReader viewing is excluded. Versioned endpoints and direct
touchscreen input are not implemented yet.

The NAS owns layout, fonts, time zone, and PNG encoding. The Kindle runs a short
POSIX shell action from KUAL, reads available telemetry, downloads one image,
checks it, displays it, and exits. An optional session listener blocks on native
power events, yields during sleep/lockscreen, and restores cached pixels after
verified lockscreen exit. It never inhibits or initiates suspend.

```text
KUAL -> device information -> GET /dashboard.png -> FastAPI -> Pillow
                            <- grayscale PNG <-
     -> validate -> atomic cache replacement -> full-screen display
```

## Milestones

1. Read-only diagnostics and a KUAL entry; collect evidence before device tuning.
2. Docker service, bounded request validation, grayscale renderer, tests, sample.
3. One-shot refresh, bounded HTTP transfer, cache preservation, display adapters.
4. Start/stop, offline KUAL page navigation, and guarded native-wake restore,
   with the Kindle framework left running. Real wake activation needs a verified profile.
5. **Deferred until physical-device diagnostics:** Wi-Fi control, scheduled suspend/wake,
   schedules, low-battery and night policy. Merely enabling a flag cannot execute
   unverified power commands.

## Boundaries and tradeoffs

- Never change Amazon's lockscreen, Special Offers, system files, or boot setup.
- No Kindle framework stop, input grab, suspend inhibitor, cron job, or polling loop.
- The optional NAS collector runs hourly and writes snapshots atomically. Failed
  sources keep their original timestamps; credentials stay on the NAS. The
  optional host exporter uses finite read-only calls, not a persistent connection.
- Start is a manual dashboard session marker plus one refresh, not a native app
  owning the display. Normal UI activity can overwrite its pixels. The normal
  power button may show advertisements. Holding the dashboard through suspend
  is explicitly not promised by this MVP.
- Wi-Fi must already be connected. Its state is observed where possible, never
  changed with guessed firmware commands. This avoids leaving a radio enabled
  after an interrupted refresh. A diagnosed adapter can be added later.
- Unknown battery/charging values are omitted, never fabricated as zero. Unknown
  dimensions fail with instructions to configure verified values.
- Display selection is FBInk, then eips. Each may vary by installed build and
  firmware. A failed FBInk draw does not trigger a second speculative backend.
- Downloads stay on the cache filesystem. A temporary backup supports rollback
  if drawing a newly validated cache fails. Failures redraw a validated previous
  cache if available. Retries require another manual action.
- The shell validates PNG signature, IHDR, bounded chunk framing, IDAT, IEND,
  encoding, and dimensions. Optional pngcheck checks CRC/decompression. Without
  pngcheck, the backend remains the decoder; shell validation is not a complete
  PNG decoder. Only fetch images from a trusted NAS.
- One mkdir lock serializes actions. Traps clean owned temporary files and locks.
  A stale lock fails closed and has a documented manual recovery procedure.
- No active flag causes an action by itself. A USB kill-switch file blocks start
  and refresh, including a recheck immediately before drawing; stop remains usable.

## Repository tree (main entry points)

```text
kindle-dashboard/
  kindle-client/extensions/dashboard/
    config.xml                 # KUAL extension discovery
    menu.json
    config.sh
    diagnostics.sh
    start.sh
    refresh-once.sh
    refresh-pages.sh
    page.sh
    sample-battery.sh
    wake-listener.sh
    restore-on-wake.sh
    stop.sh
    lib/{common,device-info,download,display,power,client,session,pages,telemetry}.sh
    lib/validate-png.awk
    cache/                     # dashboard.png created by first good refresh
    state/
    logs/
  server/
    app/{__init__,main,renderer,models,config,snapshots,collect,telemetry}.py
    app/preview.html
    tests/
    Dockerfile
    docker-compose.yml
    truenas-compose.yml
    requirements.txt
    requirements-dev.txt
    README.md
  scripts/                     # sample generator, package builder, mock tests
  docs/                        # diagnostics, recovery, hardware acceptance
  README.md
  LICENSE
  .gitignore
```

## Hardware acceptance still required

Verify screen geometry/orientation; FBInk/eips drawing and full refresh; KUAL's
exit/redraw timing; battery sources; radio state; and normal UI return. Only then
evaluate whether any supported power path can retain the dashboard without
interfering with Amazon's lockscreen. If none can, retain manual mode.
