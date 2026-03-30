from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.init_db import ping_db
from app.schemas.health import HealthResponse, WorkerHealth

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request, db: Session = Depends(get_db)) -> HealthResponse:
    database_status = "ok"
    worker_status = request.app.state.worker_manager.snapshot()

    try:
        ping_db(db)
    except Exception:  # noqa: BLE001
        database_status = "error"

    worker_health = WorkerHealth(
        running=worker_status.running,
        thread_alive=worker_status.thread_alive,
        current_job_id=worker_status.current_job_id,
        last_heartbeat=worker_status.last_heartbeat,
    )

    status = "ok" if database_status == "ok" and worker_health.thread_alive else "degraded"

    return HealthResponse(
        status=status,
        api="ok",
        database=database_status,
        worker=worker_health,
        timestamp=datetime.now(timezone.utc),
    )
