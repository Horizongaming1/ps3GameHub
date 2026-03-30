from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import JobCancelledError
from app.db.session import SessionLocal
from app.models.game import Game
from app.models.job import Job, JobStatus
from app.models.job_event import JobEvent
from app.models.target import Target
from app.services.transports.ftp import FtpTransport
from app.services.webman import WebmanService

logger = logging.getLogger(__name__)


@dataclass
class WorkerSnapshot:
    running: bool
    thread_alive: bool
    current_job_id: int | None
    last_heartbeat: datetime | None


class WorkerManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.webman_service = WebmanService(timeout_sec=settings.webman_timeout_sec)

        self._state_lock = threading.Lock()
        self._running = False
        self._current_job_id: int | None = None
        self._last_heartbeat: datetime | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self._recover_jobs_after_restart()

        self.thread = threading.Thread(target=self._run_loop, name="worker-main", daemon=True)
        self.thread.start()
        with self._state_lock:
            self._running = True

        logger.info("Worker started")

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)

        with self._state_lock:
            self._running = False
            self._current_job_id = None

        logger.info("Worker stopped")

    def snapshot(self) -> WorkerSnapshot:
        with self._state_lock:
            return WorkerSnapshot(
                running=self._running,
                thread_alive=bool(self.thread and self.thread.is_alive()),
                current_job_id=self._current_job_id,
                last_heartbeat=self._last_heartbeat,
            )

    def snapshot_dict(self) -> dict[str, object]:
        return asdict(self.snapshot())

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            self._touch_heartbeat()
            processed = self._process_next_queued_job()
            if not processed:
                self.stop_event.wait(self.settings.worker_poll_interval_sec)

        with self._state_lock:
            self._running = False

    def _process_next_queued_job(self) -> bool:
        with SessionLocal() as db:
            next_job = db.scalar(
                select(Job)
                .where(Job.status == JobStatus.QUEUED.value)
                .order_by(Job.created_at.asc())
            )
            if not next_job:
                return False
            job_id = next_job.id

        self._process_job(job_id)
        return True

    def _process_job(self, job_id: int) -> None:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                return

            if job.status != JobStatus.QUEUED.value:
                return

            if job.cancel_requested:
                self._mark_job_cancelled(db, job, "Cancelled before start")
                return

            game = db.get(Game, job.game_id)
            target = db.get(Target, job.target_id)
            if not game or not target:
                self._mark_job_failed(db, job, "Job references missing game or target")
                return

            job.status = JobStatus.RUNNING.value
            job.started_at = job.started_at or self._now()
            job.finished_at = None
            job.error_message = None
            job.attempt_count += 1
            sidecar_key = self._resolve_sidecar_key(Path(game.full_path), game.platform_guess)
            sidecar_key_size = sidecar_key.stat().st_size if sidecar_key else 0
            job.total_bytes = game.size_bytes + sidecar_key_size
            self._add_job_event(db, job.id, "job_started", "Worker started processing")
            db.commit()

            self._set_current_job(job.id)

            transport = FtpTransport(
                chunk_size=self.settings.worker_copy_chunk_size,
                timeout_sec=self.settings.ftp_timeout_sec,
            )

            last_progress_commit = 0.0
            last_cancel_check = 0.0
            cancel_flag = False

            def should_cancel() -> bool:
                nonlocal last_cancel_check, cancel_flag
                now = time.monotonic()
                if now - last_cancel_check >= 0.75:
                    db.refresh(job, attribute_names=["cancel_requested"])
                    cancel_flag = bool(job.cancel_requested) or self.stop_event.is_set()
                    last_cancel_check = now
                return cancel_flag

            def on_progress(transferred: int) -> None:
                nonlocal last_progress_commit
                job.transferred_bytes = transferred
                if job.total_bytes > 0:
                    job.progress_percent = round((transferred / job.total_bytes) * 100.0, 2)
                else:
                    job.progress_percent = 0.0

                now = time.monotonic()
                if now - last_progress_commit >= 0.75:
                    db.commit()
                    last_progress_commit = now

            try:
                source_path = Path(game.full_path)
                upload_result = self._upload_with_offset(
                    transport=transport,
                    source_path=source_path,
                    target=target,
                    offset_bytes=0,
                    on_progress=on_progress,
                    should_cancel=should_cancel,
                )

                transferred_total = upload_result.transferred_bytes
                if sidecar_key:
                    key_upload_result = self._upload_with_offset(
                        transport=transport,
                        source_path=sidecar_key,
                        target=target,
                        offset_bytes=transferred_total,
                        on_progress=on_progress,
                        should_cancel=should_cancel,
                    )
                    transferred_total += key_upload_result.transferred_bytes
                    self._add_job_event(
                        db,
                        job.id,
                        "key_file_uploaded",
                        f"Sidecar key uploaded to {key_upload_result.remote_path}",
                    )
                    db.commit()

                job.status = JobStatus.COMPLETED.value
                job.progress_percent = 100.0 if job.total_bytes > 0 else 0.0
                job.transferred_bytes = transferred_total
                job.finished_at = self._now()
                job.error_message = None

                target.capacity_used_bytes_estimate = (
                    (target.capacity_used_bytes_estimate or 0) + game.size_bytes
                )

                self._add_job_event(
                    db,
                    job.id,
                    "job_completed",
                    f"Upload completed to {upload_result.remote_path}",
                )
                db.commit()

                if job.auto_mount and target.webman_port:
                    try:
                        self.webman_service.trigger_mount(target, upload_result.remote_path)
                        self._add_job_event(
                            db,
                            job.id,
                            "auto_mount_success",
                            "webMAN mount trigger was sent",
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("webMAN mount trigger failed for job_id=%s: %s", job.id, exc)
                        self._add_job_event(
                            db,
                            job.id,
                            "auto_mount_failed",
                            f"webMAN call failed: {exc}",
                        )
                    db.commit()

            except JobCancelledError as exc:
                self._mark_job_cancelled(db, job, str(exc))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job failed job_id=%s", job.id)
                self._mark_job_failed_with_retry(db, job, str(exc))
            finally:
                self._set_current_job(None)

    def _mark_job_cancelled(self, db: Session, job: Job, message: str) -> None:
        job.status = JobStatus.CANCELLED.value
        job.finished_at = self._now()
        job.error_message = message
        self._add_job_event(db, job.id, "job_cancelled", message)
        db.commit()

    def _mark_job_failed(self, db: Session, job: Job, message: str) -> None:
        job.status = JobStatus.FAILED.value
        job.finished_at = self._now()
        job.error_message = message
        self._add_job_event(db, job.id, "job_failed", message)
        db.commit()

    def _mark_job_failed_with_retry(self, db: Session, job: Job, message: str) -> None:
        retry_allowed = (
            not job.cancel_requested and job.attempt_count <= job.max_retries
        )

        if retry_allowed:
            job.status = JobStatus.QUEUED.value
            job.error_message = f"{message} (retry scheduled)"
            self._add_job_event(db, job.id, "job_retry_scheduled", job.error_message)
        else:
            job.status = JobStatus.FAILED.value
            job.finished_at = self._now()
            job.error_message = message
            self._add_job_event(db, job.id, "job_failed", message)

        db.commit()

    def _add_job_event(self, db: Session, job_id: int, event_type: str, message: str) -> None:
        db.add(JobEvent(job_id=job_id, event_type=event_type, message=message))

    def _recover_jobs_after_restart(self) -> None:
        with SessionLocal() as db:
            running_jobs = db.scalars(
                select(Job).where(Job.status == JobStatus.RUNNING.value)
            ).all()
            for job in running_jobs:
                job.status = JobStatus.QUEUED.value
                job.error_message = "Worker restarted; job requeued"
                self._add_job_event(
                    db,
                    job.id,
                    "job_requeued",
                    "Job was running during restart and has been requeued",
                )

            queued_cancelled_jobs = db.scalars(
                select(Job).where(
                    Job.status == JobStatus.QUEUED.value,
                    Job.cancel_requested.is_(True),
                )
            ).all()
            for job in queued_cancelled_jobs:
                job.status = JobStatus.CANCELLED.value
                job.finished_at = self._now()
                self._add_job_event(
                    db,
                    job.id,
                    "job_cancelled",
                    "Cancellation was pending during restart",
                )

            if running_jobs or queued_cancelled_jobs:
                db.commit()

    def _upload_with_offset(
        self,
        transport: FtpTransport,
        source_path: Path,
        target: Target,
        offset_bytes: int,
        on_progress,
        should_cancel,
    ):
        def on_file_progress(file_transferred: int) -> None:
            on_progress(offset_bytes + file_transferred)

        return transport.upload_file(
            source_path=source_path,
            target=target,
            on_progress=on_file_progress,
            should_cancel=should_cancel,
        )

    def _resolve_sidecar_key(self, source_path: Path, platform_guess: str) -> Path | None:
        if platform_guess != "PS3":
            return None

        candidates = [
            source_path.with_suffix(".key"),
            source_path.with_suffix(".KEY"),
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _touch_heartbeat(self) -> None:
        with self._state_lock:
            self._last_heartbeat = self._now()

    def _set_current_job(self, job_id: int | None) -> None:
        with self._state_lock:
            self._current_job_id = job_id

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
