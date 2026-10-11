"""Small, versioned dashboard preferences; no executable templates or plugins."""
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .snapshots import WATCHLIST, SUPPORTED_SYMBOLS

FIELDS = {
    "weather": ["location", "temperature", "condition", "high_low", "feels_like", "precipitation", "forecast"],
    "markets": ["price", "change", "percent"],
    "nas": ["pool_health", "used_percent", "cpu_percent", "memory_percent", "alerts", "uptime", "version",
            "memory_available_gib", "memory_total_gib", "pool_free_gib", "pool_size_gib", "load_1m", "load_5m", "load_15m",
            "cpu_iowait_percent", "cpu_temperature_c", "network_rx_mbps", "network_tx_mbps", "disk_read_mbps", "disk_write_mbps",
            "scrub_state", "scrub_errors", "scrub_finished", "disk_count", "app_count", "apps_running", "apps_stopped", "alert_levels"],
    "backup": ["name", "state", "last_success", "last_run", "duration", "schedule", "progress", "transfer", "enabled"],
    "device": ["battery", "charging", "rssi", "frontlight", "uptime_seconds", "storage_free_mib", "firmware", "device", "resolution", "fetch_seconds", "fetch_failures", "last_success", "external_power", "sleep_inhibited", "power_policy"],
    "notes": ["notes"],
    "markdown": ["content"],
}
DEFAULT_FIELDS = {
    "weather": ["location", "temperature", "condition", "high_low", "precipitation", "forecast"],
    "nas": ["pool_health", "used_percent", "cpu_percent", "memory_available_gib", "alerts"],
    "markets": ["price", "change", "percent"], "backup": ["state", "last_success", "schedule"],
    "device": ["battery", "charging", "rssi"], "notes": ["notes"], "markdown": ["content"],
}


class Widget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Literal["weather", "nas", "markets", "notes", "device", "backup", "markdown"]
    key: str | None = Field(default=None, max_length=48, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(default="", max_length=40)
    row: int | None = Field(default=None, ge=1, le=12)
    column: Literal[1, 2] = 1
    width: Literal["half", "full"] = "half"
    size: Literal["small", "medium", "large"] = "medium"
    fields: list[str] | None = Field(default=None, max_length=32)
    content: str = Field(default="", max_length=4000)
    overflow: Literal["shrink", "truncate"] = "shrink"
    tickers: list[str] | None = Field(default=None, min_length=1, max_length=32)
    market_columns: Literal[2, 3] | None = None
    weather_units: Literal["source", "both"] | None = None
    notes: list[str] | None = Field(default=None, max_length=5)
    backup_index: int = Field(default=0, ge=0, le=7)

    @model_validator(mode="after")
    def valid_fields(self):
        if self.fields is not None and (len(set(self.fields)) != len(self.fields) or not set(self.fields) <= set(FIELDS[self.id])):
            raise ValueError("Unknown or duplicate widget fields")
        if self.tickers is not None and (len(set(self.tickers)) != len(self.tickers) or not set(self.tickers) <= set(SUPPORTED_SYMBOLS)):
            raise ValueError("Choose unique supported symbols")
        if self.notes is not None and any(len(line) > 100 or any(ord(c) < 32 for c in line) for line in self.notes):
            raise ValueError("Notes must be single lines of at most 100 characters")
        if self.row is not None and self.width == "full" and self.column != 1:
            raise ValueError("Full-width widgets start in the left column")
        return self


class PageLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    title: str = Field(default="Dashboard", min_length=1, max_length=40)
    density: Literal["comfortable", "compact"] = "compact"
    weather_units: Literal["source", "both"] = "both"
    market_columns: Literal[2, 3] = 2
    widgets: list[Widget] = Field(default_factory=lambda: [
        Widget(id="weather"), Widget(id="nas"),
        Widget(id="markets", width="full", size="large"),
        Widget(id="backup", size="small"), Widget(id="device", size="small"),
    ], min_length=1, max_length=12)
    tickers: list[str] = Field(default_factory=lambda: list(WATCHLIST), min_length=1, max_length=32)
    notes_title: str = Field(default="Agenda & notes", min_length=1, max_length=32)
    notes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("widgets")
    @classmethod
    def unique_widgets(cls, value):
        keys = [w.key or w.id for w in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Each widget instance needs a unique key")
        occupied = set()
        for widget in value:
            if widget.row is None:
                continue
            cells = {(widget.row, c) for c in ((1, 2) if widget.width == "full" else (widget.column,))}
            if occupied & cells:
                raise ValueError("Widget positions overlap")
            occupied.update(cells)
        return value

    @field_validator("tickers")
    @classmethod
    def known_tickers(cls, value):
        if len(set(value)) != len(value) or any(t not in SUPPORTED_SYMBOLS for t in value):
            raise ValueError("Choose unique symbols from the supported watchlist")
        return value

    @field_validator("notes")
    @classmethod
    def bounded_notes(cls, value):
        if any(len(line) > 100 or any(ord(c) < 32 for c in line) for line in value):
            raise ValueError("Notes must be single lines of at most 100 characters")
        return value


PAGE_IDS = ("overview", "weather", "markets-1", "markets-2", "nas")


class Layout(PageLayout):
    pages: dict[Literal["weather", "markets-1", "markets-2", "nas"], PageLayout] = Field(default_factory=dict)
    page_order: list[Literal["overview", "weather", "markets-1", "markets-2", "nas"]] = Field(default_factory=lambda: list(PAGE_IDS), min_length=1, max_length=5)
    refresh_minutes: int = Field(default=60, ge=5, le=1440)
    night_minutes: int = Field(default=240, ge=15, le=1440)
    rotation_minutes: int = Field(default=0, ge=0, le=1440)

    @field_validator("page_order")
    @classmethod
    def unique_pages(cls, value):
        if len(value) != len(set(value)): raise ValueError("Duplicate pages")
        return value

    @model_validator(mode="before")
    @classmethod
    def migrate_usage(cls, value):
        if isinstance(value, dict) and isinstance(value.get("widgets"), list) and any(isinstance(w, dict) and w.get("id") == "chatgpt" for w in value["widgets"]):
            value = dict(value)
            value["widgets"] = [w for w in value["widgets"] if not isinstance(w, dict) or w.get("id") != "chatgpt"]
            if not value["widgets"]: value["widgets"] = [{"id": "device"}]
        return value

    def for_page(self, page):
        if page == "overview": return self
        if page in self.pages: return self.pages[page]
        widgets = {"weather": [Widget(id="weather", width="full", size="large"),
                               Widget(id="device", size="small"), Widget(id="nas", size="small")],
                   "nas": [Widget(id="nas", width="full", size="large", fields=[
                       "pool_health", "used_percent", "pool_free_gib", "cpu_percent", "cpu_temperature_c",
                       "memory_available_gib", "network_rx_mbps", "network_tx_mbps", "alerts", "uptime",
                       "apps_running", "scrub_state"]),
                           Widget(id="backup", width="full", fields=["state", "last_success", "last_run", "duration", "schedule", "transfer"]),
                           Widget(id="device", width="full", size="small")],
                   "markets-1": [Widget(id="markets", width="full", size="large")],
                   "markets-2": [Widget(id="markets", width="full", size="large")]}
        cut = (len(self.tickers)+1)//2
        tickers = self.tickers[:cut] if page == "markets-1" else self.tickers[cut:] if page == "markets-2" else self.tickers
        return PageLayout(title={"weather":"Weather","nas":"Home server","markets-1":"Markets 1","markets-2":"Markets 2"}[page],
                          widgets=widgets[page], tickers=tickers or self.tickers, weather_units=self.weather_units)


class LayoutStore:
    def __init__(self, path=""):
        self.path = Path(path) if path else None
        self.lock = Lock()
        self.value = Layout()
        if self.path and self.path.exists():
            try:
                with self.path.open("rb") as stream:
                    raw = stream.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Layout too large")
                self.value = Layout.model_validate_json(raw)
            except (ValueError, OSError):
                logging.getLogger("dashboard").warning("Invalid saved layout; using defaults")

    def get(self):
        with self.lock:
            return self.value.model_copy(deep=True)

    def save(self, value):
        with self.lock:
            if self.path is None:
                raise OSError("DASHBOARD_LAYOUT_PATH must be configured to save layouts")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                 prefix=".layout-", delete=False) as stream:
                    temporary = stream.name
                    stream.write(value.model_dump_json())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            self.value = value.model_copy(deep=True)
