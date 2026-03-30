from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.game import Game
from app.models.job import Job, JobStatus
from app.models.job_event import JobEvent
from app.models.target import Target
from app.schemas.job import JobCreateRequest, JobEventOut, JobGameOut, JobOut, JobTargetOut

router = APIRouter(tags=["jobs"])
settings = get_settings()


@router.post("/jobs/cache", response_model=JobOut, status_code=201)
def create_cache_job(payload: JobCreateRequest, db: Session = Depends(get_db)) -> JobOut:
    game = db.get(Game, payload.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    target = db.get(Target, payload.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    free_bytes_estimate = (
        (target.capacity_total_bytes or 0)
        - (target.capacity_reserved_bytes or 0)
        - (target.capacity_used_bytes_estimate or 0)
    )

    if target.capacity_total_bytes > 0 and game.size_bytes > free_bytes_estimate:
        raise HTTPException(
            status_code=409,
            detail=(
                "Not enough estimated free capacity on target: "
                f"required={game.size_bytes}, available={max(free_bytes_estimate, 0)}"
            ),
        )

    job = Job(
        game_id=game.id,
        target_id=target.id,
        auto_mount=payload.auto_mount,
        status=JobStatus.QUEUED.value,
        total_bytes=game.size_bytes,
        max_retries=settings.worker_max_retries,
    )
    db.add(job)
    db.flush()

    db.add(
        JobEvent(
            job_id=job.id,
            event_type="job_queued",
            message="Job added to queue",
        )
    )

    db.commit()
    return _build_job_out(db, job.id)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    jobs = db.scalars(select(Job).order_by(Job.created_at.desc())).all()
    return [_build_job_out(db, job.id, include_events=False) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    return _build_job_out(db, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
        return _build_job_out(db, job.id)

    if job.status == JobStatus.QUEUED.value:
        job.cancel_requested = True
        job.status = JobStatus.CANCELLED.value
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = "Cancelled before execution"
        db.add(JobEvent(job_id=job.id, event_type="job_cancelled", message=job.error_message))
    else:
        job.cancel_requested = True
        db.add(
            JobEvent(
                job_id=job.id,
                event_type="cancel_requested",
                message="Cancellation requested while job is running",
            )
        )

    db.commit()
    return _build_job_out(db, job.id)


def _build_job_out(db: Session, job_id: int, include_events: bool = True) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    game = db.get(Game, job.game_id)
    target = db.get(Target, job.target_id)
    if not game or not target:
        raise HTTPException(status_code=500, detail="Broken job reference")

    events = []
    if include_events:
        events = [
            JobEventOut.model_validate(event)
            for event in db.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job.id)
                .order_by(JobEvent.created_at.asc())
            ).all()
        ]

    return JobOut(
        id=job.id,
        status=JobStatus(job.status),
        auto_mount=job.auto_mount,
        progress_percent=job.progress_percent,
        transferred_bytes=job.transferred_bytes,
        total_bytes=job.total_bytes,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        cancel_requested=job.cancel_requested,
        attempt_count=job.attempt_count,
        max_retries=job.max_retries,
        created_at=job.created_at,
        updated_at=job.updated_at,
        game=JobGameOut(
            id=game.id,
            filename=game.filename,
            full_path=game.full_path,
            size_bytes=game.size_bytes,
        ),
        target=JobTargetOut(
            id=target.id,
            name=target.name,
            ip_address=target.ip_address,
            ftp_port=target.ftp_port,
            target_path=target.target_path,
        ),
        events=events,
    )
