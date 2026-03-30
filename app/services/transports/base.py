from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.models.target import Target


@dataclass
class UploadResult:
    remote_path: str
    transferred_bytes: int


class TargetTransport(ABC):
    @abstractmethod
    def upload_file(
        self,
        source_path: Path,
        target: Target,
        on_progress: Callable[[int], None],
        should_cancel: Callable[[], bool],
    ) -> UploadResult:
        raise NotImplementedError
