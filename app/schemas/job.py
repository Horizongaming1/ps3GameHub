from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    game_id: int
    target_id: int
    auto_mount: bool = False


class JobEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    message: str
    created_at: datetime


class JobGameOut(BaseModel):
    id: int
    filename: str
    full_path: str
    size_bytes: int


class JobTargetOut(BaseModel):
    id: int
    name: str
    ip_address: str
    ftp_port: int
    target_path: str


class JobOut(BaseModel):
    id: int
    status: JobStatus
    auto_mount: bool
    progress_percent: float
    transferred_bytes: int
    total_bytes: int
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    cancel_requested: bool
    attempt_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime
    game: JobGameOut
    target: JobTargetOut
    events: list[JobEventOut] = Field(default_factory=list)
