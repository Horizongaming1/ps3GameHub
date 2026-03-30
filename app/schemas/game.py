from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    full_path: str
    size_bytes: int
    platform_guess: str
    title_guess: str
    game_id_guess: str | None
    modified_at: datetime
