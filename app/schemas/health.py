from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkerHealth(BaseModel):
    running: bool
    thread_alive: bool
    current_job_id: int | None
    last_heartbeat: datetime | None


class HealthResponse(BaseModel):
    status: str
    api: str
    database: str
    worker: WorkerHealth
    timestamp: datetime
