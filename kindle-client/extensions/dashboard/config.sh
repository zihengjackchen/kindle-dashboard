#!/bin/sh
# Edit defaults inside := below. Environment overrides are useful for mock tests.
: "${DASHBOARD_URL:=http://192.168.1.20:8080/dashboard.png}"
: "${API_TOKEN:=}"
: "${CONNECT_TIMEOUT_SECONDS:=10}"
: "${DOWNLOAD_TIMEOUT_SECONDS:=30}"
: "${MAX_IMAGE_BYTES:=4194304}"
: "${MAX_LOG_BYTES:=65536}"
: "${DISPLAY_BACKEND:=auto}"       # auto | fbink | eips
: "${HTTP_CLIENT:=auto}"           # auto | curl | wget
: "${FBINK_BIN:=fbink}"            # absolute path if not on PATH
: "${EIPS_BIN:=eips}"
: "${SCREEN_WIDTH:=}"             # verified overrides, e.g. 1236
: "${SCREEN_HEIGHT:=}"            # verified overrides, e.g. 1648
: "${DEVICE_MODEL:=}"
: "${BATTERY_CAPACITY_FILE:=}"     # optional diagnostic-confirmed sysfs path
: "${BATTERY_STATUS_FILE:=}"
: "${KUAL_SETTLE_SECONDS:=2}"      # let KUAL's closing repaint finish
: "${DISABLE_FILE:=/mnt/us/dashboard-disable}"
: "${MOCK_MODE:=0}"
: "${MOCK_BATTERY:=73}"
: "${MOCK_CHARGING:=0}"
: "${MOCK_WIDTH:=1236}"
: "${MOCK_HEIGHT:=1648}"
: "${DEVICE_ID:=kindle}"          # your own short label, never a serial number
: "${SEND_TELEMETRY:=1}"          # optional diagnostics piggyback on image fetches
: "${MOCK_RSSI:=-55}"
# Native sleep remains in charge. Enable only after the profile has been observed
# on this exact model/firmware; see docs/native-wake.md. No power writes occur.
: "${WAKE_RESTORE:=0}"
: "${WAKE_VERIFIED_MODEL:=}"
: "${WAKE_VERIFIED_FIRMWARE:=}"
: "${WAKE_UNLOCK_SOURCE:=}"
: "${WAKE_UNLOCK_PROPERTY:=}"
: "${WAKE_UNLOCK_VALUE:=}"
: "${WAKE_SETTLE_SECONDS:=1}"
: "${LIPC_WAIT_BIN:=lipc-wait-event}"
: "${DEFAULT_PAGE:=overview}"
# Reserved policy values only. No scheduler or power command is implemented.
: "${ENABLE_EXPERIMENTAL_POWER:=0}"
: "${AUTO_REFRESH:=0}"
: "${NORMAL_INTERVAL_MINUTES:=60}"
: "${NIGHT_INTERVAL_MINUTES:=240}"
: "${LOW_BATTERY_PERCENT:=20}"
