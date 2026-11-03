"""Input limits shared with the shell client."""

from typing import Literal
from pydantic import BaseModel, Field, field_validator

MIN_DIMENSION = 320
MAX_DIMENSION = 2560  # At most 6.6 million grayscale pixels.
PAGE_IDS = ("overview", "weather", "markets-1", "markets-2", "nas")


class DashboardRequest(BaseModel):
    page: Literal["overview", "weather", "markets-1", "markets-2", "nas"] = "overview"
    width: int = Field(default=1236, gt=0, le=100_000)
    height: int = Field(default=1648, gt=0, le=100_000)
    battery: int | None = Field(default=None, ge=0, le=100)
    charging: bool | None = None
    external_power: bool | None = None
    sleep_inhibited: bool | None = None
    power_policy: Literal["native-sleep", "plugged-in", "foreground"] | None = None
    device: str = Field(default="unknown", max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    device_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    rssi: int | None = Field(default=None, ge=-127, le=-1)
    fetch_seconds: int | None = Field(default=None, ge=0, le=86400)
    fetch_failures: int | None = Field(default=None, ge=0, le=999999)
    last_success_epoch: int | None = Field(default=None, ge=0, le=4102444800)
    frontlight: int | None = Field(default=None, ge=0, le=100)
    uptime_seconds: int | None = Field(default=None, ge=0, le=2147483647)
    storage_free_mib: int | None = Field(default=None, ge=0, le=1000000)
    firmware: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")

    @field_validator("width", "height")
    @classmethod
    def clamp_dimension(cls, value: int) -> int:
        return max(MIN_DIMENSION, min(MAX_DIMENSION, value))


class ReportPreviewRequest(DashboardRequest):
    number: int = Field(default=1, ge=1, le=27)
    font_size: int = Field(default=30, ge=24, le=40)
