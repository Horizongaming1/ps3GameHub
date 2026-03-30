from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.game import Game
from app.schemas.game import GameOut

router = APIRouter(tags=["games"])


@router.get("/games", response_model=list[GameOut])
def list_games(db: Session = Depends(get_db)) -> list[Game]:
    query = select(Game).order_by(Game.title_guess.asc(), Game.filename.asc())
    return list(db.scalars(query).all())
