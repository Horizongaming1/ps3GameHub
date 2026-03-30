from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    ip_address: IPv4Address | IPv6Address
    ftp_port: int = Field(default=21, ge=1, le=65535)
    webman_port: int | None = Field(default=None, ge=1, le=65535)
    ftp_username: str | None = Field(default=None, max_length=120)
    ftp_password: SecretStr | None = None
    target_path: str = Field(default="/dev_hdd0/PS3ISO", min_length=1, max_length=255)

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("target_path must start with '/'")
        return value


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip_address: str
    ftp_port: int
    webman_port: int | None
    ftp_username: str | None
    target_path: str
    has_password: bool
    capacity_total_bytes: int
    capacity_reserved_bytes: int
    capacity_used_bytes_estimate: int
    created_at: datetime
    updated_at: datetime


class CapacityUpdate(BaseModel):
    total_bytes: int = Field(ge=0)
    reserved_bytes: int = Field(ge=0)
    used_bytes_estimate: int = Field(ge=0)


class CapacityOut(BaseModel):
    target_id: int
    total_bytes: int
    reserved_bytes: int
    used_bytes_estimate: int
    free_bytes_estimate: int
