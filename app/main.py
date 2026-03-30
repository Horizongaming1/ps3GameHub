from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.scanner import GameScanner
from app.worker.manager import WorkerManager

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PS3 Cache API",
    version="0.1.0",
    description="NAS-side cache orchestration service for legal PS3 backup handling.",
)
app.include_router(api_router)

ui_dir = Path(__file__).resolve().parent / "ui"
app.mount("/ui/static", StaticFiles(directory=ui_dir / "static"), name="ui-static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()

    app.state.scanner = GameScanner(settings)
    app.state.worker_manager = WorkerManager(settings)

    if settings.scan_on_startup:
        try:
            with SessionLocal() as db:
                summary = app.state.scanner.scan(db)
            logger.info(
                "Startup scan complete: scanned=%s added=%s updated=%s removed=%s",
                summary.scanned_files,
                summary.added,
                summary.updated,
                summary.removed,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Startup scan failed")

    app.state.worker_manager.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    app.state.worker_manager.stop()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ui", include_in_schema=False)
def ui_index() -> FileResponse:
    return FileResponse(ui_dir / "index.html")


@app.get("/ui/", include_in_schema=False)
def ui_index_trailing() -> FileResponse:
    return FileResponse(ui_dir / "index.html")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "request_error",
            "message": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Internal server error",
        },
    )
