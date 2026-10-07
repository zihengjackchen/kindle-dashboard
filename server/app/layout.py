"""Small, versioned dashboard preferences; no executable templates or plugins."""
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .snapshots import WATCHLIST, SUPPORTED_SYMBOLS


class Widget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Literal["weather", "nas", "markets", "notes", "device", "chatgpt"]
    width: Literal["half", "full"] = "half"
    size: Literal["small", "medium", "large"] = "medium"


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    title: str = Field(default="At a glance", min_length=1, max_length=40)
    density: Literal["comfortable", "compact"] = "compact"
    weather_units: Literal["source", "both"] = "both"
    market_columns: Literal[2, 3] = 2
    widgets: list[Widget] = Field(default_factory=lambda: [
        Widget(id="weather"), Widget(id="nas"),
        Widget(id="markets", width="full", size="large"),
        Widget(id="notes", size="small"), Widget(id="device", size="small"),
    ], min_length=1, max_length=6)
    tickers: list[str] = Field(default_factory=lambda: list(WATCHLIST), min_length=1, max_length=32)
    notes_title: str = Field(default="Agenda & notes", min_length=1, max_length=32)
    notes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("widgets")
    @classmethod
    def unique_widgets(cls, value):
        if len({w.id for w in value}) != len(value):
            raise ValueError("Each widget can appear only once")
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


class LayoutStore:
    def __init__(self, path=""):
        self.path = Path(path) if path else None
        self.lock = Lock()
        self.value = Layout()
        if self.path and self.path.exists():
            try:
                with self.path.open("rb") as stream:
                    raw = stream.read(16385)
                if len(raw) > 16384:
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
                    stream.write(value.model_dump_json(indent=2))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            self.value = value.model_copy(deep=True)
