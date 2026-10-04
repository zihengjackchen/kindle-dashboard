# Daylight 0.1.0

Standalone KUAL dashboard and Dockerized NAS renderer, with five grayscale pages:
overview, weather, two watchlist pages, and NAS health. Includes an offline KUAL
carousel, bounded downloads, PNG validation, cache rollback, start/stop, kill
switch, device diagnostics and opt-in verified native-wake restoration.

This release adds browser preview, matching configuration generation, optional
NAS-side Open-Meteo/Twelve Data/Coinbase collectors, a read-only TrueNAS exporter,
source freshness labels, optional contact telemetry and battery measurement tools.

The public Kindle ZIP has no private credentials. Configure it using docs/setup.md.
Container build/publish status is available in GitHub Actions. This release makes
no claim of physical Kindle or TrueNAS acceptance: model/firmware display behavior,
wake profile, provider entitlements and NAS version must be verified at installation.
Amazon Special Offers and native sleep remain unchanged. Touchscreen page turning,
brokerage integration, automatic Kindle refresh and direct kernel suspend are deferred.
