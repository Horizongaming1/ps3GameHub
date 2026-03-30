from __future__ import annotations

from ftplib import FTP, all_errors, error_perm
import logging
from pathlib import Path, PurePosixPath
from typing import Callable

from app.core.exceptions import JobCancelledError
from app.models.target import Target
from app.services.transports.base import TargetTransport, UploadResult

logger = logging.getLogger(__name__)


class FtpTransport(TargetTransport):
    def __init__(self, chunk_size: int, timeout_sec: float) -> None:
        self.chunk_size = chunk_size
        self.timeout_sec = timeout_sec

    def upload_file(
        self,
        source_path: Path,
        target: Target,
        on_progress: Callable[[int], None],
        should_cancel: Callable[[], bool],
    ) -> UploadResult:
        remote_dir = target.target_path.rstrip("/") or "/"
        remote_path = str(PurePosixPath(remote_dir) / source_path.name)

        transferred = 0
        ftp = FTP()
        try:
            ftp.connect(target.ip_address, target.ftp_port, timeout=self.timeout_sec)
            ftp.login(target.ftp_username or "anonymous", target.ftp_password or "anonymous@")
            self._ensure_remote_dir(ftp, remote_dir)

            with source_path.open("rb") as source:
                data_sock = ftp.transfercmd(f"STOR {remote_path}")
                try:
                    while True:
                        if should_cancel():
                            raise JobCancelledError("Cancellation requested")

                        chunk = source.read(self.chunk_size)
                        if not chunk:
                            break

                        data_sock.sendall(chunk)
                        transferred += len(chunk)
                        on_progress(transferred)
                finally:
                    try:
                        data_sock.close()
                    except OSError:
                        pass

            ftp.voidresp()
            logger.info(
                "FTP upload finished: target_id=%s remote_path=%s bytes=%s",
                target.id,
                remote_path,
                transferred,
            )
            return UploadResult(remote_path=remote_path, transferred_bytes=transferred)

        except JobCancelledError:
            logger.info("FTP upload cancelled for target_id=%s", target.id)
            try:
                ftp.delete(remote_path)
            except all_errors:
                logger.warning("Unable to clean up partial remote file: %s", remote_path)
            raise
        except all_errors as exc:
            raise RuntimeError(f"FTP upload failed: {exc}") from exc
        finally:
            try:
                ftp.quit()
            except all_errors:
                try:
                    ftp.close()
                except all_errors:
                    pass

    def _ensure_remote_dir(self, ftp: FTP, remote_dir: str) -> None:
        current = ""
        for segment in PurePosixPath(remote_dir).parts:
            if segment in {"", "/"}:
                continue
            current = f"{current}/{segment}" if current else f"/{segment}"
            try:
                ftp.mkd(current)
            except error_perm as exc:
                if not str(exc).startswith("550"):
                    raise
