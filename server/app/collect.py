"""Optional NAS-only collectors. No network calls occur in the PNG request path."""
import argparse
import json
import logging
import os
import signal
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .snapshots import Forecast, NAS, Quote, Snapshot, WATCHLIST, SUPPORTED_SYMBOLS, Weather, load_snapshot

LOG = logging.getLogger("collector")
STOP = Event()


def get_json(url, headers=None):
    request = Request(url, headers={"User-Agent": "kindle-dashboard/1.0", "Accept": "application/json", **(headers or {})})
    with urlopen(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Provider response too large")
    return json.loads(raw)


def condition(code):
    if code == 0: return "Clear sky"
    if code in (1, 2): return "Partly cloudy"
    if code == 3: return "Overcast"
    if code in (45, 48): return "Fog"
    if code in (51, 53, 55, 56, 57): return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "Rain"
    if code in (71, 73, 75, 77, 85, 86): return "Snow"
    if code in (95, 96, 99): return "Thunderstorms"
    return "Conditions unavailable"


def weather(env, fetch=get_json):
    lat, lon = float(env["WEATHER_LATITUDE"]), float(env["WEATHER_LONGITUDE"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates")
    unit = env.get("WEATHER_UNIT", "F")
    if unit not in ("F", "C"): raise ValueError("Invalid weather unit")
    params = dict(latitude=lat, longitude=lon, timezone=env.get("DASHBOARD_TIMEZONE", "UTC"),
                  temperature_unit="fahrenheit" if unit == "F" else "celsius", timeformat="unixtime",
                  current="temperature_2m,apparent_temperature,weather_code",
                  daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                  forecast_days=4)
    data = fetch("https://api.open-meteo.com/v1/forecast?" + urlencode(params))
    current, daily = data["current"], data["daily"]
    as_of = datetime.fromtimestamp(current["time"], timezone.utc)
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(env.get("DASHBOARD_TIMEZONE", "UTC"))
    return Weather(source="Open-Meteo", as_of=as_of, valid_until=as_of+timedelta(hours=2),
                   location=env.get("WEATHER_LOCATION") or f"{lat:.2f}, {lon:.2f}", unit=unit,
                   temperature=current["temperature_2m"], feels_like=current["apparent_temperature"],
                   condition=condition(current["weather_code"]), high=daily["temperature_2m_max"][0],
                   low=daily["temperature_2m_min"][0], precipitation_percent=daily["precipitation_probability_max"][0],
                   forecast=[Forecast(day=datetime.fromtimestamp(daily["time"][i], tz).strftime("%a"),
                                      condition=condition(daily["weather_code"][i]),
                                      high=daily["temperature_2m_max"][i], low=daily["temperature_2m_min"][i])
                             for i in range(1, min(4, len(daily["time"])))])


def equity(symbol, env, fetch=get_json):
    provider_symbol = env.get("TWELVE_DATA_SP500_SYMBOL", "SPX") if symbol == "S&P 500" else symbol
    params = dict(symbol=provider_symbol, apikey=env["TWELVE_DATA_API_KEY"], prepost="false")
    data = fetch("https://api.twelvedata.com/quote?" + urlencode(params))
    if data.get("status") == "error": raise ValueError("Provider rejected instrument or entitlement")
    if data.get("symbol") != provider_symbol or data.get("currency") != "USD":
        raise ValueError("Unexpected instrument or currency")
    as_of = datetime.fromtimestamp(int(data.get("last_quote_at") or data["timestamp"]), timezone.utc)
    # Provider/account entitlement controls delay. Default conservatively to delayed.
    return Quote(source="Twelve Data", symbol=symbol, price=data["close"], change=data["change"],
                 change_percent=data["percent_change"], as_of=as_of, valid_until=as_of+timedelta(hours=2),
                 session="regular" if data["is_market_open"] is True else "closed",
                 basis="previous close", delayed=env.get("MARKET_DATA_DELAYED", "1") != "0")


def crypto(symbol, fetch=get_json):
    data = fetch(f"https://api.exchange.coinbase.com/products/{symbol}/stats")
    price, opening = float(data["last"]), float(data["open"])
    if opening <= 0: raise ValueError("Invalid 24h opening value")
    # Stats has no trade timestamp: explicitly label the timestamp as observation time.
    now = datetime.now(timezone.utc)
    return Quote(source="Coinbase / observed", symbol=symbol, price=price, change=price-opening,
                 change_percent=100*(price/opening-1), as_of=now, valid_until=now+timedelta(hours=2),
                 session="24h", basis="24h")


def finnhub_equity(symbol, env, fetch=get_json):
    provider_symbol = env.get("FINNHUB_SP500_SYMBOL", "^GSPC") if symbol == "S&P 500" else symbol
    data = fetch("https://finnhub.io/api/v1/quote?" + urlencode({"symbol": provider_symbol}),
                 headers={"X-Finnhub-Token": env["FINNHUB_API_KEY"]})
    if data.get("error") or not data.get("t") or not data.get("c"):
        raise ValueError("Finnhub quote unavailable")
    as_of = datetime.fromtimestamp(int(data["t"]), timezone.utc)
    return Quote(source="Finnhub", symbol=symbol, price=data["c"], change=data["d"],
                 change_percent=data["dp"], as_of=as_of, valid_until=as_of+timedelta(hours=2),
                 session="unknown", basis="previous close", delayed=env.get("MARKET_DATA_DELAYED", "1") != "0")


def save_snapshot(path, snapshot):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="snapshot-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(snapshot.model_dump_json(indent=2))
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def collect_once(env=None, fetch=get_json, wait=STOP.wait):
    env = os.environ if env is None else env
    path = env.get("DASHBOARD_SNAPSHOT_PATH", "/data/snapshot.json")
    previous = load_snapshot(path)
    # Never promote a design fixture into live source data.
    if previous.demo: previous = Snapshot()
    result = previous.model_dump()
    errors = []
    if env.get("WEATHER_LATITUDE") and env.get("WEATHER_LONGITUDE"):
        try: result["weather"] = weather(env, fetch)
        except Exception:
            errors.append("weather")
            LOG.warning("Weather fetch failed; retaining previous observation")
    quotes = {q.symbol: q for q in previous.quotes}
    if env.get("FINNHUB_API_KEY") or env.get("TWELVE_DATA_API_KEY"):
        requested = (env.get("MARKET_SYMBOLS") or ",".join(WATCHLIST[:10])).split(",")
        symbols = list(dict.fromkeys(s.strip() for s in requested if s.strip() in SUPPORTED_SYMBOLS and s.strip() not in WATCHLIST[10:]))
        use_finnhub = bool(env.get("FINNHUB_API_KEY"))
        for index, symbol in enumerate(symbols):
            if index and wait(2 if use_finnhub else 8): break
            try: quotes[symbol] = (finnhub_equity if use_finnhub else equity)(symbol, env, fetch)
            except Exception:
                errors.append(symbol)
                LOG.warning("Quote unavailable for %s; retaining previous observation", symbol)
    if env.get("CRYPTO_ENABLED", "0") == "1":
        for symbol in WATCHLIST[10:]:
            try: quotes[symbol] = crypto(symbol, fetch)
            except Exception:
                errors.append(symbol)
                LOG.warning("Crypto unavailable for %s; retaining previous observation", symbol)
    nas_path = env.get("NAS_SNAPSHOT_PATH", "")
    if nas_path:
        try:
            with Path(nas_path).open("rb") as stream: raw = stream.read(65537)
            if len(raw) > 65536: raise ValueError("NAS snapshot too large")
            result["nas"] = NAS.model_validate_json(raw)
        except Exception:
            errors.append("nas")
            LOG.warning("NAS export unavailable; retaining previous observation")
    result["quotes"] = list(quotes.values())
    save_snapshot(path, Snapshot.model_validate(result))
    LOG.info("Collection complete; unavailable sources=%d", len(errors))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="Run on the NAS only, hourly by default")
    parser.add_argument("--healthcheck", action="store_true", help="Check collection progress without contacting providers")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    interval = max(900, min(86400, int(os.getenv("COLLECT_INTERVAL_SECONDS", "3600"))))
    if args.healthcheck:
        raise SystemExit(0 if collection_healthy(os.getenv("DASHBOARD_SNAPSHOT_PATH", "/data/snapshot.json"), interval) else 1)
    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, lambda *_: STOP.set())
    while not STOP.is_set():
        collect_once()
        if not args.loop or STOP.wait(interval): break


def collection_healthy(path, interval, now=None):
    """Fresh file publication proves the loop ran, not that every provider is fresh."""
    try:
        age = (now or datetime.now(timezone.utc).timestamp()) - Path(path).stat().st_mtime
        return -60 <= age <= max(900, min(86400, interval)) + 300
    except OSError:
        return False


if __name__ == "__main__": main()
