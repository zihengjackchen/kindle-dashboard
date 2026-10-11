"""Bounded persisted source snapshots. Rendering never performs network work."""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

WATCHLIST = ("S&P 500", "VOO", "VGT", "META", "AMZN", "GOOG", "AMD", "PYPL", "SOFI", "GRAB", "BTC-USD", "ETH-USD")
SUPPORTED_SYMBOLS = tuple(dict.fromkeys(WATCHLIST + ("AAPL", "TSLA", "GOOGL", "MSFT", "NFLX", "NVDA", "ADBE", "SCHD", "SPY", "DIA", "QQQ", "IWM", "TLT", "GLD", "DBC")))


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=60)
    as_of: AwareDatetime
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def valid_dates(self):
        if self.valid_until < self.as_of:
            raise ValueError("valid_until precedes as_of")
        return self

    def status(self, now: datetime) -> str:
        if self.as_of > now:
            return "CHECK TIME"
        return "STALE" if now > self.valid_until else "CURRENT"


class Forecast(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    day: str = Field(max_length=12)
    condition: str = Field(max_length=40)
    high: float = Field(ge=-150, le=160)
    low: float = Field(ge=-150, le=160)


class Weather(Record):
    location: str = Field(min_length=1, max_length=60)
    unit: Literal["F", "C"]
    temperature: float = Field(ge=-150, le=160)
    feels_like: float | None = Field(default=None, ge=-150, le=160)
    condition: str = Field(max_length=50)
    high: float = Field(ge=-150, le=160)
    low: float = Field(ge=-150, le=160)
    precipitation_percent: int = Field(ge=0, le=100)
    forecast: list[Forecast] = Field(default_factory=list, max_length=4)


class Quote(Record):
    symbol: str = Field(min_length=1, max_length=16)
    price: float = Field(ge=0, le=1e12)
    change: float
    change_percent: float
    currency: Literal["USD"] = "USD"
    session: Literal["regular", "closed", "premarket", "afterhours", "24h", "unknown"]
    basis: Literal["previous close", "24h"]
    delayed: bool = False


class Backup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=80)
    enabled: bool = True
    state: str = Field(default="UNKNOWN", max_length=24)
    last_run: AwareDatetime | None = None
    last_success: AwareDatetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    percent: float | None = Field(default=None, ge=0, le=100)
    schedule: str = Field(default="Unknown", max_length=80)
    transfer: str = Field(default="", max_length=180)


class NAS(Record):
    name: str = Field(max_length=40)
    version: str = Field(max_length=40)
    pool_health: Literal["ONLINE", "DEGRADED", "FAULTED", "UNKNOWN"]
    used_percent: float | None = Field(default=None, ge=0, le=100)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    alerts: int = Field(ge=0, le=10000)
    uptime: str = Field(max_length=40)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict, max_length=40)
    backups: list[Backup] = Field(default_factory=list, max_length=8)


class UsageWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    used_percent: float = Field(ge=0, le=100)
    window_minutes: int | None = Field(default=None, ge=1, le=525600)
    resets_at: AwareDatetime | None = None


class CodexUsage(Record):
    source: Literal["Codex account"] = "Codex account"
    limit_name: Literal["Codex", "Account"] = "Codex"
    primary: UsageWindow | None = None
    secondary: UsageWindow | None = None
    lifetime_tokens: int | None = Field(default=None, ge=0, le=9007199254740991)
    peak_daily_tokens: int | None = Field(default=None, ge=0, le=9007199254740991)
    latest_day: date | None = None
    latest_day_tokens: int | None = Field(default=None, ge=0, le=9007199254740991)
    current_streak_days: int | None = Field(default=None, ge=0, le=100000)
    longest_streak_days: int | None = Field(default=None, ge=0, le=100000)
    longest_running_turn_seconds: int | None = Field(default=None, ge=0, le=31536000)

    def status(self, now):
        status = super().status(now)
        if status == "CURRENT" and any(w and w.resets_at and w.resets_at <= now for w in (self.primary, self.secondary)):
            return "STALE"
        return status


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    demo: bool = False
    weather: Weather | None = None
    quotes: list[Quote] = Field(default_factory=list, max_length=32)
    nas: NAS | None = None
    codex: CodexUsage | None = None
    @model_validator(mode="before")
    @classmethod
    def discard_legacy_usage(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("chatgpt", None)
        return value

    @model_validator(mode="after")
    def unique_quotes(self):
        symbols = [q.symbol for q in self.quotes]
        if len(symbols) != len(set(symbols)) or not set(symbols) <= set(SUPPORTED_SYMBOLS):
            raise ValueError("Duplicate or unknown symbol")
        for q in self.quotes:
            if q.basis != ("24h" if q.symbol in ("BTC-USD", "ETH-USD") else "previous close"):
                raise ValueError("Incorrect change basis")
        return self


def load_snapshot(path: str, usage_path: str = "") -> Snapshot:
    snapshot = _load_snapshot(path)
    if usage_path:
        try:
            with Path(usage_path).open("rb") as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise ValueError("Usage snapshot exceeds 16 KiB")
            snapshot.codex = CodexUsage.model_validate_json(raw)
        except FileNotFoundError:
            snapshot.codex = None
        except (OSError, ValueError):
            logging.getLogger("dashboard").warning("Usage snapshot invalid; usage unavailable")
            snapshot.codex = None
    return snapshot


def _load_snapshot(path: str) -> Snapshot:
    if not path:
        return Snapshot()
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(262145)
        if len(raw) > 262144:
            raise ValueError("Snapshot exceeds 256 KiB")
        return Snapshot.model_validate_json(raw)
    except FileNotFoundError:
        return Snapshot()
    except (OSError, ValueError):
        logging.getLogger("dashboard").error("Snapshot missing or invalid; rendering unavailable data")
        return Snapshot()
