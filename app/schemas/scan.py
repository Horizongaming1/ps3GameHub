from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ScanResponse(BaseModel):
    scanned_files: int
    added: int
    updated: int
    removed: int
    finished_at: datetime
