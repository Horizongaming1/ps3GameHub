from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.game import Game
from app.services.metadata import extract_game_metadata

logger = logging.getLogger(__name__)


@dataclass
class ScanSummary:
    scanned_files: int
    added: int
    updated: int
    removed: int
    finished_at: datetime


class GameScanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.library_root = Path(settings.library_root)

    def scan(self, db: Session) -> ScanSummary:
        root = self.library_root
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Library root not found or not a directory: {root}")

        root_resolved = root.resolve()

        existing_games = {
            game.full_path: game for game in db.scalars(select(Game)).all()
        }

        discovered_paths: set[str] = set()
        scanned_files = 0
        added = 0
        updated = 0

        for file_path in self._iter_iso_files(root):
            try:
                resolved = file_path.resolve()
            except FileNotFoundError:
                continue

            if os.path.commonpath([str(root_resolved), str(resolved)]) != str(root_resolved):
                logger.warning("Skipping file outside library root: %s", resolved)
                continue

            stat = resolved.stat()
            scanned_files += 1

            metadata = extract_game_metadata(resolved.name)
            full_path = str(resolved)
            discovered_paths.add(full_path)

            game = existing_games.get(full_path)
            if game:
                game.filename = resolved.name
                game.size_bytes = stat.st_size
                game.modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                game.platform_guess = str(metadata["platform_guess"])
                game.title_guess = str(metadata["title_guess"])
                game.game_id_guess = metadata["game_id_guess"]
                updated += 1
            else:
                db.add(
                    Game(
                        filename=resolved.name,
                        full_path=full_path,
                        size_bytes=stat.st_size,
                        platform_guess=str(metadata["platform_guess"]),
                        title_guess=str(metadata["title_guess"]),
                        game_id_guess=metadata["game_id_guess"],
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    )
                )
                added += 1

        removed = 0
        for full_path, game in existing_games.items():
            if full_path not in discovered_paths:
                db.delete(game)
                removed += 1

        db.commit()

        summary = ScanSummary(
            scanned_files=scanned_files,
            added=added,
            updated=updated,
            removed=removed,
            finished_at=datetime.now(timezone.utc),
        )

        logger.info(
            "Scan completed: scanned=%s added=%s updated=%s removed=%s",
            summary.scanned_files,
            summary.added,
            summary.updated,
            summary.removed,
        )

        return summary

    def _iter_iso_files(self, root: Path):
        iterator = root.rglob("*") if self.settings.scan_recursive else root.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() == ".iso":
                yield path
