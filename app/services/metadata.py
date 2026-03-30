from __future__ import annotations

from pathlib import Path
import re

GAME_ID_PATTERN = re.compile(r"([A-Z]{4})[-_\s]?(\d{5})")
PS3_PREFIXES = {
    "BCES",
    "BCUS",
    "BLES",
    "BLUS",
    "NPEA",
    "NPEB",
    "NPEE",
    "NPJA",
    "NPUB",
    "NPUA",
}
PS2_PREFIXES = {"SCES", "SCUS", "SLES", "SLUS"}


def extract_game_metadata(
    filename: str,
    folder_platform: str | None = None,
) -> dict[str, str | None]:
    stem = Path(filename).stem
    normalized = stem.upper()

    match = GAME_ID_PATTERN.search(normalized)
    game_id = f"{match.group(1)}{match.group(2)}" if match else None

    platform = _guess_platform(
        game_id=game_id,
        filename=normalized,
        folder_platform=folder_platform,
    )
    title = _guess_title(stem=stem, game_id=game_id)

    return {
        "platform_guess": platform,
        "title_guess": title,
        "game_id_guess": game_id,
    }


def _guess_platform(
    game_id: str | None,
    filename: str,
    folder_platform: str | None = None,
) -> str:
    if folder_platform in {"PS3", "PS2", "PACKS"}:
        return folder_platform

    if game_id:
        prefix = game_id[:4]
        if prefix in PS3_PREFIXES or prefix.startswith("BL"):
            return "PS3"
        if prefix in PS2_PREFIXES or prefix.startswith("SL") or prefix.startswith("SC"):
            return "PS2"

    if "PS3" in filename:
        return "PS3"
    if "PS2" in filename:
        return "PS2"
    return "unknown"


def _guess_title(stem: str, game_id: str | None) -> str:
    title = stem
    if game_id:
        title = re.sub(game_id, "", title, flags=re.IGNORECASE)

    title = re.sub(r"[\[\](){}]", " ", title)
    title = title.replace("_", " ").replace("-", " ")
    title = re.sub(r"\s+", " ", title).strip()

    return title or stem
