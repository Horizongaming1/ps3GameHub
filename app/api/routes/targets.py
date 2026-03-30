from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.target import Target
from app.schemas.target import CapacityOut, CapacityUpdate, TargetCreate, TargetOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["targets"])


@router.get("/targets", response_model=list[TargetOut])
def list_targets(db: Session = Depends(get_db)) -> list[Target]:
    return list(db.scalars(select(Target).order_by(Target.name.asc())).all())


@router.post("/targets", response_model=TargetOut, status_code=201)
def create_target(payload: TargetCreate, db: Session = Depends(get_db)) -> Target:
    existing = db.scalar(select(Target).where(Target.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail=f"Target with name '{payload.name}' already exists")

    target = Target(
        name=payload.name,
        ip_address=str(payload.ip_address),
        ftp_port=payload.ftp_port,
        webman_port=payload.webman_port,
        ftp_username=payload.ftp_username,
        ftp_password=payload.ftp_password.get_secret_value() if payload.ftp_password else None,
        target_path=payload.target_path,
    )

    db.add(target)
    db.commit()
    db.refresh(target)

    logger.info(
        "Created target id=%s name=%s ip=%s ftp_port=%s",
        target.id,
        target.name,
        target.ip_address,
        target.ftp_port,
    )

    return target


@router.get("/targets/{target_id}/capacity", response_model=CapacityOut)
def get_target_capacity(target_id: int, db: Session = Depends(get_db)) -> CapacityOut:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    free = max(
        0,
        (target.capacity_total_bytes or 0)
        - (target.capacity_reserved_bytes or 0)
        - (target.capacity_used_bytes_estimate or 0),
    )

    return CapacityOut(
        target_id=target.id,
        total_bytes=target.capacity_total_bytes,
        reserved_bytes=target.capacity_reserved_bytes,
        used_bytes_estimate=target.capacity_used_bytes_estimate,
        free_bytes_estimate=free,
    )


@router.post("/targets/{target_id}/capacity", response_model=CapacityOut)
def update_target_capacity(
    target_id: int,
    payload: CapacityUpdate,
    db: Session = Depends(get_db),
) -> CapacityOut:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if payload.reserved_bytes + payload.used_bytes_estimate > payload.total_bytes:
        raise HTTPException(
            status_code=400,
            detail="reserved_bytes + used_bytes_estimate must not exceed total_bytes",
        )

    target.capacity_total_bytes = payload.total_bytes
    target.capacity_reserved_bytes = payload.reserved_bytes
    target.capacity_used_bytes_estimate = payload.used_bytes_estimate
    db.commit()

    return get_target_capacity(target_id, db)
