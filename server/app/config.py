"""Small environment-only configuration; no database or remote data sources."""

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    api_token: str = ""
    timezone: str = "UTC"
    font_path: str = ""
    snapshot_path: str = ""
    state_path: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            api_token=os.getenv("API_TOKEN", ""),
            timezone=os.getenv("DASHBOARD_TIMEZONE", "UTC"),
            font_path=os.getenv("DASHBOARD_FONT_PATH", ""),
            snapshot_path=os.getenv("DASHBOARD_SNAPSHOT_PATH", ""),
            state_path=os.getenv("DASHBOARD_STATE_PATH", ""),
        )
        ZoneInfo(settings.timezone)  # Fail at startup for a misspelled timezone.
        return settings
