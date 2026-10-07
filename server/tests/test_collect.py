from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import pytest
from app.collect import collect_once, crypto, equity, save_snapshot, weather
from app.snapshots import Snapshot, load_snapshot


def weather_response():
    return {"current": {"time": 1700000000, "temperature_2m": 62, "apparent_temperature": 60, "weather_code": 2},
            "daily": {"time": [1700000000+i*86400 for i in range(4)], "weather_code": [2, 3, 61, 0],
                      "temperature_2m_max": [65]*4, "temperature_2m_min": [45]*4, "precipitation_probability_max": [20]*4}}


def test_weather_preserves_source_time():
    urls = []
    def fetch(url): urls.append(url); return weather_response()
    data = weather({"WEATHER_LATITUDE": "47", "WEATHER_LONGITUDE": "-122", "WEATHER_UNIT": "F"}, fetch)
    assert data.temperature == 62 and data.condition == "Partly cloudy"
    assert len(data.forecast) == 3
    assert data.as_of == datetime.fromtimestamp(1700000000, timezone.utc)
    assert parse_qs(urlsplit(urls[0]).query)["temperature_unit"] == ["fahrenheit"]


def test_equity_uses_quote_timestamp_and_explicit_delay():
    raw = dict(symbol="VOO", currency="USD", close="600", change="5", percent_change="0.84",
               timestamp=1700000000, last_quote_at=1700000100, is_market_open=False)
    quote = equity("VOO", {"TWELVE_DATA_API_KEY": "hidden"}, lambda _: raw)
    assert quote.delayed and quote.session == "closed" and quote.basis == "previous close"
    assert quote.as_of.timestamp() == 1700000100
    with pytest.raises(ValueError): equity("AMD", {"TWELVE_DATA_API_KEY": "hidden"}, lambda _: raw)


def test_crypto_calculates_24h_change():
    quote = crypto("BTC-USD", lambda _: {"open": "100", "last": "110"})
    assert quote.change == 10 and quote.change_percent == pytest.approx(10)
    assert quote.basis == "24h" and "observed" in quote.source


def test_outage_retains_each_record_and_its_original_timestamp(tmp_path):
    path = tmp_path / "snapshot.json"
    saved = Snapshot(weather=weather({"WEATHER_LATITUDE": "0", "WEATHER_LONGITUDE": "0"}, lambda _: weather_response()),
                     quotes=[crypto("BTC-USD", lambda _: {"open": "100", "last": "110"})])
    save_snapshot(path, saved)
    def fail(_): raise OSError("provider unavailable with secret=do-not-log")
    errors = collect_once({"DASHBOARD_SNAPSHOT_PATH": str(path), "WEATHER_LATITUDE": "0", "WEATHER_LONGITUDE": "0", "CRYPTO_ENABLED": "1"}, fail)
    assert "weather" in errors and "BTC-USD" in errors
    assert load_snapshot(str(path)) == saved


def test_demo_is_never_merged_into_live_data(tmp_path):
    path = tmp_path / "snapshot.json"
    save_snapshot(path, Snapshot(demo=True, quotes=[crypto("BTC-USD", lambda _: {"open": "100", "last": "110"})]))
    collect_once({"DASHBOARD_SNAPSHOT_PATH": str(path)})
    assert load_snapshot(str(path)) == Snapshot()


def test_partial_markets_failure_and_rate_spacing(tmp_path):
    waits = []
    def fetch(url):
        symbol = parse_qs(urlsplit(url).query)["symbol"][0]
        if symbol != "AMD": return {"status": "error"}
        return dict(symbol="AMD", currency="USD", close=100, change=1, percent_change=1,
                    timestamp=1700000000, is_market_open=True)
    path = tmp_path / "snapshot.json"
    errors = collect_once({"DASHBOARD_SNAPSHOT_PATH": str(path), "TWELVE_DATA_API_KEY": "hidden"}, fetch, lambda seconds: waits.append(seconds))
    assert len(errors) == 9 and waits == [8]*9
    assert [q.symbol for q in load_snapshot(str(path)).quotes] == ["AMD"]


def test_collection_health_detects_stalled_loop_without_fetching(tmp_path):
    from app.collect import collection_healthy
    import os
    path = tmp_path / 'snapshot.json'
    assert not collection_healthy(path, 900, now=5000)
    path.write_text('{}')
    os.utime(path, (4000, 4000))
    assert collection_healthy(path, 900, now=5000)
    assert not collection_healthy(path, 900, now=5300)
    assert not collection_healthy(path, 900, now=3000)


def test_finnhub_header_auth_timestamp_and_failure():
    from app.collect import finnhub_equity
    requests = []
    def fetch(url, headers):
        requests.append((url, headers))
        return {"c": 200, "d": 2, "dp": 1.01, "t": 1700000000}
    quote = finnhub_equity("AAPL", {"FINNHUB_API_KEY": "private-test"}, fetch)
    assert quote.symbol == "AAPL" and quote.price == 200
    assert quote.as_of.timestamp() == 1700000000 and quote.session == "unknown"
    assert "private-test" not in requests[0][0]
    assert requests[0][1] == {"X-Finnhub-Token": "private-test"}
    with pytest.raises(ValueError):
        finnhub_equity("AAPL", {"FINNHUB_API_KEY": "private-test"}, lambda *a, **k: {"c": 0, "t": 0})


def test_extended_watchlist_spacing_and_usage_retention(tmp_path):
    from datetime import timedelta
    from app.snapshots import ChatGPTUsage
    from app.collect import finnhub_equity
    now = datetime.now(timezone.utc)
    usage = ChatGPTUsage(source="OpenAI / PC sync", as_of=now, valid_until=now+timedelta(hours=2), lifetime_tokens=123)
    usage_path = tmp_path/"chatgpt.json"
    usage_path.write_text(usage.model_dump_json())
    snapshot_path = tmp_path/"snapshot.json"
    waits = []
    def fetch(url, headers):
        if "SPY" in url: raise OSError("secret must not be logged")
        return {"c": 200, "d": 2, "dp": 1.01, "t": 1700000000}
    env = {"FINNHUB_API_KEY": "private", "MARKET_SYMBOLS": "AAPL,AAPL,MSFT,SPY,UNKNOWN,BTC-USD",
           "DASHBOARD_SNAPSHOT_PATH": str(snapshot_path), "CHATGPT_SNAPSHOT_PATH": str(usage_path)}
    errors = collect_once(env, fetch, waits.append)
    snapshot = load_snapshot(str(snapshot_path))
    assert [q.symbol for q in snapshot.quotes] == ["AAPL", "MSFT"]
    assert waits == [2, 2] and errors == ["SPY"]
    assert snapshot.chatgpt == usage
    usage_path.write_text("invalid")
    collect_once(env, fetch, lambda _: False)
    assert load_snapshot(str(snapshot_path)).chatgpt == usage
