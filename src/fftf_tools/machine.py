"""Shared machine-block helper for FFTF tool waves.

Wave 1 (brief-pack / claim-gate / script-strip / picture-sync / thumb-pack)
was not on main when this helper landed. Both waves should keep these
top-level field names so the JSON blocks compose:

- episode_id
- sources
- fences
- asset_index
- distro_blocked

``distro_blocked`` is always the boolean ``true``. This module cannot
unlock Distro, publish, or record a platform API call.
"""

from __future__ import annotations

import json
from pathlib import Path

CHANNEL_NAME = "From Fiction to Fact"
CHANNEL_SHORT = "FFTF"

MACHINE_FIELDS = (
    "episode_id",
    "sources",
    "fences",
    "asset_index",
    "distro_blocked",
)

# Caller extras that must never be stored. Distro stays locked.
_DROPPED_EXTRAS = {
    "distro_blocked",
    "distro_unlocked",
    "unlock_distro",
    "publish",
    "upload",
}

BASE_FENCES = (
    {
        "id": "no-publish",
        "text": "Do not publish.",
        "locked": True,
    },
    {
        "id": "no-distro",
        "text": "Do not unlock Distro.",
        "locked": True,
    },
    {
        "id": "no-platform-api",
        "text": "No YouTube or Spotify API calls.",
        "locked": True,
    },
    {
        "id": "no-invented-sources",
        "text": "Do not invent primary sources.",
        "locked": True,
    },
)


def episode_id_for(ep: int) -> str:
    if ep < 1:
        raise ValueError("episode number must be >= 1")
    return f"ep{ep:02d}"


def machine_block(
    *,
    episode_id: str,
    sources: list | None = None,
    fences: list | None = None,
    asset_index: list | None = None,
    **extra: object,
) -> dict:
    """Build a machine block. ``distro_blocked`` is forced to True."""
    if not str(episode_id).strip():
        raise ValueError("episode_id is required")
    cleaned = {k: v for k, v in extra.items() if k not in _DROPPED_EXTRAS}
    block: dict = {
        "episode_id": episode_id,
        "sources": list(sources or []),
        "fences": list(fences or []),
        "asset_index": list(asset_index or []),
    }
    for key, value in cleaned.items():
        if key not in block:
            block[key] = value
    block["distro_blocked"] = True
    return block


def write_machine_json(path: Path | str, block: dict) -> Path:
    """Write machine JSON. Re-locks ``distro_blocked`` at the file boundary."""
    path = Path(path)
    payload = dict(block)
    payload["distro_blocked"] = True
    for key in ("episode_id", "sources", "fences", "asset_index"):
        if key not in payload:
            raise ValueError(f"machine block missing {key}")
    for key in ("sources", "fences", "asset_index"):
        if not isinstance(payload[key], list):
            raise ValueError(f"{key} must be a list")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
