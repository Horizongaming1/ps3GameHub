from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    ftp_port: Mapped[int] = mapped_column(Integer, default=21)
    webman_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ftp_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ftp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_path: Mapped[str] = mapped_column(String(255), nullable=False)

    capacity_total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    capacity_reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    capacity_used_bytes_estimate: Mapped[int] = mapped_column(BigInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    @property
    def has_password(self) -> bool:
        return bool(self.ftp_password)
