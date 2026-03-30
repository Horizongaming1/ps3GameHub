from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.scan import ScanResponse

router = APIRouter(tags=["scanner"])


@router.post("/scan", response_model=ScanResponse)
def trigger_scan(request: Request, db: Session = Depends(get_db)) -> ScanResponse:
    try:
        summary = request.app.state.scanner.scan(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ScanResponse(
        scanned_files=summary.scanned_files,
        added=summary.added,
        updated=summary.updated,
        removed=summary.removed,
        finished_at=summary.finished_at,
    )
