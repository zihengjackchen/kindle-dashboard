import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response

from .config import Settings
from .models import DashboardRequest
from .renderer import render_dashboard
from .snapshots import load_snapshot
from .telemetry import ContactStore

logger = logging.getLogger("dashboard")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Kindle Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    contacts = ContactStore(settings.state_path)

    def authenticate(authorization: Annotated[str | None, Header()] = None):
        if settings.api_token:
            expected = f"Bearer {settings.api_token}".encode()
            if not secrets.compare_digest((authorization or "").encode(), expected):
                raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/dashboard.png", dependencies=[Depends(authenticate)])
    def dashboard(data: Annotated[DashboardRequest, Query()]):
        contacts.contact(data)
        try:
            png = render_dashboard(data, settings)
        except Exception:
            logger.exception("PNG generation failed for dimensions=%sx%s", data.width, data.height)
            raise HTTPException(500, "Image generation failed") from None
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store", "X-Dashboard-Page": data.page})

    @app.get("/status", dependencies=[Depends(authenticate)])
    def status(response: Response):
        response.headers["Cache-Control"] = "no-store"
        now = datetime.now(timezone.utc)
        snapshot = load_snapshot(settings.snapshot_path)
        records = {"weather": snapshot.weather, "nas": snapshot.nas}
        records.update({quote.symbol: quote for quote in snapshot.quotes})
        return {"service": "ok", "server_time": now.isoformat(), "devices": contacts.snapshot(),
                "sources": {key: {"status": value.status(now), "as_of": value.as_of.isoformat(),
                                  "valid_until": value.valid_until.isoformat()} if value else None
                            for key, value in records.items()}}

    @app.get("/", include_in_schema=False)
    def preview():
        return Response(Path(__file__).with_name("preview.html").read_text(encoding="utf-8"),
                        media_type="text/html", headers={"Cache-Control": "no-store"})

    return app


app = create_app()
