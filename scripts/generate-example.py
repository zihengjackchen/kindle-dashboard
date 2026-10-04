"""Run from the repository root; uses the same renderer as the endpoint."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.config import Settings  # noqa: E402
from app.models import DashboardRequest  # noqa: E402
from app.models import PAGE_IDS  # noqa: E402
from app.renderer import render_dashboard  # noqa: E402
from demo_snapshot import demo_snapshot  # noqa: E402

fixture = demo_snapshot()
example_dir = ROOT / "docs" / "previews"
example_dir.mkdir(exist_ok=True)
for page in PAGE_IDS:
    png = render_dashboard(
        DashboardRequest(page=page, width=1236, height=1648, battery=73, charging=False, device="paperwhite"),
        Settings(timezone="America/Los_Angeles"),
        datetime(2026, 10, 1, 9, 41, tzinfo=ZoneInfo("America/Los_Angeles")),
        snapshot=fixture,
    )
    (example_dir / f"{page}.png").write_bytes(png)
    if page == "overview":
        (ROOT / "docs" / "example-dashboard.png").write_bytes(png)
(example_dir / "sample-snapshot.json").write_text(fixture.model_dump_json(indent=2), encoding="utf-8")
print(example_dir)
