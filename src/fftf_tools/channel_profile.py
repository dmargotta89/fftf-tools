"""FFTF channel profile for Edit and Distro.

Agents do not freestyle these locks. Display name is From Fiction to Fact
(FFTF only). Runners stay dry-run unless a later wave is told otherwise,
and even then this profile does not authorize a live upload.
"""

from __future__ import annotations

from fftf_tools.machine import CHANNEL_NAME, CHANNEL_SHORT

CHANNEL_SLUG = "from-fiction-to-fact"
DISPLAY_NAME = CHANNEL_NAME
DISPLAY_NAME_SHORT = CHANNEL_SHORT

YT_THUMB = (1280, 720)
IG_THUMB = (1080, 1350)
IG_FIT = "contain_pad"

CHROME_LOCK = {
    "font": "Liberation Sans Bold",
    "drip": 0,
    "underline": "full yellow",
    "badge": "FFTF",
    "pill": "EPISODE",
}

# Checklist ceilings for a PC pack. They are not an upload client.
_GIB = 1024 ** 3
_MIB = 1024 ** 2
SIZE_CAPS = {
    "yt_long": 128 * _GIB,
    "short": 1 * _GIB,
    "podcast_audio": 200 * _MIB,
    "podcast_extended": 500 * _MIB,
    "cover": 10 * _MIB,
    "thumb": 5 * _MIB,
}

ORDERED_WAVES = ("yt-long", "shorts", "podcast")
SEPARATE_WAVES = ("podcast-extended",)

LOUDNESS = {"voice_lufs": -14.0, "true_peak_dbtp": -1.0, "duck_music_db": -12.0}

ALLOWED_LICENSES = ("PD", "gov", "cia", "other")


def checklist_row(item_id: str, path, cap_key: str) -> dict:
    """One size-cap row. Missing files are not ok; they do not raise."""
    cap = SIZE_CAPS[cap_key]
    if path is None or not path.is_file():
        return {
            "id": item_id,
            "path": None if path is None else str(path),
            "bytes": None,
            "cap_bytes": cap,
            "ok": False,
        }
    size = path.stat().st_size
    return {
        "id": item_id,
        "path": str(path),
        "bytes": size,
        "cap_bytes": cap,
        "ok": size <= cap,
    }
