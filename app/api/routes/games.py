from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.game import Game
from app.schemas.game import GameOut

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameOut])
def list_games(
    search: str | None = Query(default=None, description="Search in filename, title or game id"),
    sort_by: Literal["id", "filename", "title", "modified_at", "size_bytes", "platform"] = "id",
    sort_dir: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
) -> list[Game]:
    query: Select[tuple[Game]] = select(Game)

    if search:
        normalized = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(Game.filename).like(normalized),
                func.lower(Game.title_guess).like(normalized),
                func.lower(Game.full_path).like(normalized),
                func.lower(func.coalesce(Game.game_id_guess, "")).like(normalized),
            )
        )

    sort_mapping = {
        "id": Game.id,
        "filename": Game.filename,
        "title": Game.title_guess,
        "modified_at": Game.modified_at,
        "size_bytes": Game.size_bytes,
        "platform": Game.platform_guess,
    }

    sort_column = sort_mapping[sort_by]
    if sort_dir == "desc":
        query = query.order_by(sort_column.desc(), Game.id.desc())
    else:
        query = query.order_by(sort_column.asc(), Game.id.asc())

    return list(db.scalars(query).all())
