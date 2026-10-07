import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .config import Settings
from .models import DashboardRequest
from .renderer import render_dashboard
from .snapshots import SUPPORTED_SYMBOLS, load_snapshot
from .telemetry import ContactStore
from .layout import Layout, LayoutStore

logger = logging.getLogger("dashboard")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Kindle Dashboard", docs_url=None, redoc_url=None, openapi_url=None)
    contacts = ContactStore(settings.state_path)
    layouts = LayoutStore(settings.layout_path)

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
            png = render_dashboard(data, settings, None, None, layouts.get())
        except Exception:
            logger.exception("PNG generation failed for dimensions=%sx%s", data.width, data.height)
            raise HTTPException(500, "Image generation failed") from None
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store", "X-Dashboard-Page": data.page})

    def editor_auth(authorization: Annotated[str | None, Header()] = None):
        if not settings.api_token:
            raise HTTPException(503, "Set API_TOKEN before enabling the layout editor")
        authenticate(authorization)

    async def read_layout(request: Request):
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 16384:
                raise HTTPException(413, "Layout is limited to 16 KiB")
            raw.extend(chunk)
        try:
            return Layout.model_validate_json(bytes(raw))
        except ValidationError:
            raise HTTPException(422, "Invalid layout: check widget IDs, sizes, symbols and note lengths") from None

    @app.get("/layout", dependencies=[Depends(editor_auth)])
    def get_layout(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {"layout": layouts.get(), "defaults": Layout(), "tickers": SUPPORTED_SYMBOLS,
                "can_save": bool(settings.layout_path)}

    @app.put("/layout", dependencies=[Depends(editor_auth)])
    async def save_layout(request: Request):
        value = await read_layout(request)
        try:
            await run_in_threadpool(layouts.save, value)
        except OSError:
            logger.exception("Layout save failed")
            raise HTTPException(503, "Layout could not be saved; previous layout retained") from None
        logger.info("Dashboard layout saved")
        return Response(value.model_dump_json(), media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.post("/preview.png", dependencies=[Depends(editor_auth)])
    async def draft_preview(request: Request, data: Annotated[DashboardRequest, Query()]):
        value = await read_layout(request)
        try:
            png = await run_in_threadpool(render_dashboard, data, settings, None, None, value)
        except Exception:
            logger.exception("Layout preview generation failed")
            raise HTTPException(500, "Preview generation failed") from None
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/status", dependencies=[Depends(authenticate)])
    def status(response: Response):
        response.headers["Cache-Control"] = "no-store"
        now = datetime.now(timezone.utc)
        snapshot = load_snapshot(settings.snapshot_path)
        records = {"weather": snapshot.weather, "nas": snapshot.nas, "chatgpt": snapshot.chatgpt}
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
