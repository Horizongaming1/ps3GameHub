from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.models import game, job, job_event, target  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def ping_db(db: Session) -> bool:
    db.execute(text("SELECT 1"))
    return True
