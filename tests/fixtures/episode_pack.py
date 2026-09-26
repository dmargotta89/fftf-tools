"""Build a small on-disk episode pack for edit-pass and distro tests.

Media is generated locally. Nothing here opens a socket.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw

from fftf_tools.channel_profile import CHROME_LOCK, IG_FIT
from fftf_tools.episode_pack import hash_path, md5_file, spoken_word_count, wording_hash
from fftf_tools.thumb_pack import IG_SIZE, YT_SIZE, contain_pad

NARRATION = (
    "The files were on the desk in June.\n"
    "A story said otherwise.\n"
    "The record shows the files.\n"
)
NOTES = "Desk paraphrase for Source Notes only. Do not put this sentence on screen."
CARD = "June 17, 1972."
QUOTE = "The record shows the files."
APPROVED_SOURCE = "National Archives, Record Group 460."
TITLE = "The files were on the desk"


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rate = 16000
    count = int(rate * seconds)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            value = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / rate))
            frames += struct.pack("<h", value)
        handle.writeframes(frames)


def _good(path: Path) -> None:
    image = Image.new("RGB", (160, 90), (70, 110, 140))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 100, 70), fill=(40, 70, 90))
    image.save(path)


def _frames(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(24):
        path = directory / f"frame_{index:03d}.png"
        if index == 1:
            Image.new("RGB", (160, 90), (0, 0, 0)).save(path)
        elif index >= 22:
            Image.new("RGB", (160, 90), (250, 250, 250)).save(path)
        else:
            # Index 0 is a valid-looking frame on purpose. The sampler must not pick it.
            _good(path)


def _thumbs(root: Path) -> tuple[Path, Path]:
    yt = root / "thumbs" / "ep05-A-LIVE.png"
    ig = root / "thumbs" / "ep05-A-LIVE-ig45.png"
    yt.parent.mkdir(parents=True, exist_ok=True)
    card = Image.new("RGB", YT_SIZE, (18, 18, 20))
    draw = ImageDraw.Draw(card)
    draw.rectangle((80, 80, 1200, 640), fill=(32, 48, 64))
    draw.line((120, 560, 1160, 560), fill=(240, 200, 40), width=8)
    draw.text((120, 180), "FFTF", fill=(245, 245, 245))
    draw.text((120, 240), "EPISODE", fill=(245, 245, 245))
    card.save(yt)
    contain_pad(card, IG_SIZE).save(ig)
    return yt, ig


def _asset(asset_id: str, rel: str, role: str, license_name: str, path: Path, type_name: str) -> dict:
    return {
        "asset_id": asset_id,
        "path": rel,
        "role": role,
        "type": type_name,
        "license": license_name,
        "sha256": hash_path(path),
    }


def build_episode_pack(
    root: Path,
    *,
    script_stamped: bool = True,
    drop_live_thumbs: bool = False,
    wording_hash_override: str | None = None,
    blank_license: bool = False,
    caption_equals_notes: bool = False,
    display_name: str | None = None,
    with_extended: bool = False,
    extended_go: bool = False,
) -> Path:
    """Write a gate-clean pack, then apply the requested mutations."""
    root.mkdir(parents=True, exist_ok=True)
    _frames(root / "sources" / "camA")
    hero = root / "sources" / "hero.png"
    hero.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 180), (180, 90, 40)).save(hero)
    vo = root / "vo" / "narration.wav"
    _wav(vo)
    narration = root / "vo" / "narration-only.md"
    narration.write_text(NARRATION, encoding="utf-8")
    script = root / "script" / "draft.md"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f"STAMP: Daniel\n\n{NARRATION}", encoding="utf-8")
    (root / "vo" / "vo-timing.md").write_text(
        "## Cold open\n\n" + NARRATION + "\n[p]\n",
        encoding="utf-8",
    )
    yt, ig = _thumbs(root)
    if drop_live_thumbs and yt.is_file():
        yt.unlink()

    review = root / "verifier" / "review.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        "# Verifier review\n\nStatus: PASS\n\nNarration-only wording is pinned. Claims did not move.\n",
        encoding="utf-8",
    )
    words = spoken_word_count(NARRATION)
    pinned = wording_hash_override if wording_hash_override is not None else wording_hash(NARRATION)
    _dump(
        root / "verifier" / "verdict.json",
        {
            "review_path": "verifier/review.md",
            "status": "PASS",
            "spoken_word_count": words,
            "wording_hash": pinned,
            "match_vs_narration": "MATCH",
            "claims_moved": False,
        },
    )
    card_text = NOTES if caption_equals_notes else CARD
    _dump(
        root / "caption_safe.json",
        {
            "episode_id": "ep05",
            "notes": NOTES,
            "cards": [{"id": "lt1", "text": card_text, "source": "caption_safe"}],
            "quote_cards": [{"id": "q1", "text": QUOTE, "verifier_approved": True}],
        },
    )
    (root / "picture-qc.md").write_text(
        "# Picture QC — ep05\n\n"
        "Frozen frames: none.\n"
        "Wrong stills: none.\n"
        "Jump cuts: none.\n"
        "A/V drift: none.\n\n"
        "QC note: holds stay inside the beat windows.\n",
        encoding="utf-8",
    )
    pc = root / "pc-pack"
    pc.mkdir(parents=True, exist_ok=True)
    (pc / "EPISODE.txt").write_text("ep05\n", encoding="utf-8")
    _dump(
        root / "distro-go.json",
        {"kind": "distro", "episode_id": "ep05", "approved": True, "approved_by": "Distro"},
    )
    cover = root / "cover" / "ep05-cover-LOCKED.png"
    cover.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (300, 300), (20, 20, 20)).save(cover)

    masters = root / "masters"
    masters.mkdir(parents=True, exist_ok=True)
    files = {
        "longform": masters / "ep05-long.mp4",
        "A": masters / "ep05-short-A.mp4",
        "B": masters / "ep05-short-B.mp4",
        "C": masters / "ep05-short-C.mp4",
        "D": masters / "ep05-short-D.mp4",
        "podcast": masters / "ep05-podcast.m4a",
    }
    for key, path in files.items():
        path.write_bytes(f"FFTF-STANDIN-{key}\n".encode("utf-8"))
    extended_path = masters / "ep05-podcast-extended.m4a"
    if with_extended:
        extended_path.write_bytes(b"FFTF-STANDIN-extended\n")
    if extended_go:
        _dump(
            root / "podcast-extended-go.json",
            {
                "kind": "podcast_extended",
                "episode_id": "ep05",
                "approved": True,
                "approved_by": "Distro",
            },
        )

    assets = [
        _asset("camA", "sources/camA", "primary", "PD", root / "sources" / "camA", "camera"),
        _asset("hero", "sources/hero.png", "hero", "PD", hero, "still"),
        _asset("vo", "vo/narration.wav", "vo", "other", vo, "audio"),
        _asset("narration", "vo/narration-only.md", "narration", "other", narration, "text"),
        _asset("thumb-ig", "thumbs/ep05-A-LIVE-ig45.png", "thumb-ig", "other", ig, "thumb"),
        _asset("cover", "cover/ep05-cover-LOCKED.png", "cover", "other", cover, "thumb"),
        _asset("longform", "masters/ep05-long.mp4", "master", "other", files["longform"], "master"),
        _asset("short-A", "masters/ep05-short-A.mp4", "short", "other", files["A"], "master"),
        _asset("short-B", "masters/ep05-short-B.mp4", "short", "other", files["B"], "master"),
        _asset("short-C", "masters/ep05-short-C.mp4", "short", "other", files["C"], "master"),
        _asset("short-D", "masters/ep05-short-D.mp4", "short", "other", files["D"], "master"),
        _asset("podcast", "masters/ep05-podcast.m4a", "podcast", "other", files["podcast"], "audio"),
    ]
    if yt.is_file():
        assets.append(_asset("thumb-yt", "thumbs/ep05-A-LIVE.png", "thumb-yt", "other", yt, "thumb"))
    if with_extended:
        assets.append(
            _asset("podcast-extended", "masters/ep05-podcast-extended.m4a", "podcast", "other", extended_path, "audio")
        )
    if blank_license:
        for asset in assets:
            if asset["asset_id"] == "hero":
                asset["license"] = ""
    _dump(root / "asset_index.json", {"episode_id": "ep05", "assets": assets})

    description = (
        "The files were on the desk in June.\n\n"
        "Sources:\n"
        f"{APPROVED_SOURCE}\n\n"
        "From Fiction to Fact (FFTF).\n"
    )
    manifest = {
        "episode_id": "ep05",
        "channel": "from-fiction-to-fact",
        "display_name_lock": display_name or "From Fiction to Fact",
        "display_name_short": "FFTF",
        "title": TITLE,
        "vo": {
            "path": "vo/narration.wav",
            "timing_path": "vo/vo-timing.md",
            "narration_path": "vo/narration-only.md",
            "target_lufs": -14,
            "immutable": True,
            "rewritten_after_stamp": False,
        },
        "script_path": "script/draft.md",
        "verdict": {"path": "verifier/verdict.json"},
        "stamps": {
            "script_stamped": script_stamped,
            "script_stamped_by": "Daniel" if script_stamped else "",
            "thumb_live": True,
            "thumb_yt_path": "thumbs/ep05-A-LIVE.png",
            "thumb_ig_path": "thumbs/ep05-A-LIVE-ig45.png",
            "thumb_fixed_sha256": hash_path(yt) if yt.is_file() else "",
            "thumb_ig_sha256": hash_path(ig),
            "thumb_md5": md5_file(yt) if yt.is_file() else "",
            "thumb_ig_fit": IG_FIT,
            "hook_text": "The files",
            "opt_letter": "A",
            "chrome_lock": dict(CHROME_LOCK),
            "soft_parked": False,
        },
        "timeline": [
            {
                "beat_id": "cold_open",
                "t_start_s": 0.0,
                "t_end_s": 0.8,
                "kind": "vo+broll",
                "broll": [{"asset_id": "hero", "role": "hero", "max_s": 0.8}],
            }
        ],
        "sources": [
            {"asset_id": "camA", "path": "sources/camA", "type": "camera", "role": "primary"},
            {"asset_id": "hero", "path": "sources/hero.png", "type": "still", "role": "hero"},
        ],
        "edit": {
            "backend": "ffmpeg",
            "color": {"mode": "match_to_ref", "ref_policy": "auto"},
            "audio": {"duck_music_db": -12, "voice_lufs": -14, "true_peak_dbtp": -1.0},
            "pacing": {"from": "vo_timing", "min_cut_s": 0.8, "max_still_hold_s": 5.0},
        },
        "music": {"enabled": False},
        "picture_qc": {"passed": True, "note_path": "picture-qc.md"},
        "masters": {
            "longform": {"path": "masters/ep05-long.mp4", "sha256": hash_path(files["longform"])},
            "shorts": [
                {"id": letter, "path": f"masters/ep05-short-{letter}.mp4", "sha256": hash_path(files[letter])}
                for letter in ("A", "B", "C", "D")
            ],
            "podcast_yt_length": {"path": "masters/ep05-podcast.m4a", "sha256": hash_path(files["podcast"])},
            "podcast_extended": {
                "path": "masters/ep05-podcast-extended.m4a" if with_extended else None,
                "sha256": hash_path(extended_path) if with_extended else None,
                "separate_go": True,
                "go_path": "podcast-extended-go.json" if extended_go else None,
            },
        },
        "cover": {
            "path": "cover/ep05-cover-LOCKED.png",
            "locked": True,
            "sha256": hash_path(cover),
        },
        "meta": {
            "title": TITLE,
            "description": description,
            "shorts_hooks": {
                "A": "The files were on the desk in June.",
                "B": "A story said otherwise.",
                "C": "The record shows the files.",
                "D": "The files were on the desk in June.",
            },
            "sources_list": [APPROVED_SOURCE],
            "inherits_locked_narration": True,
            "claim_gated": True,
        },
        "approved_sources": [APPROVED_SOURCE],
        "asset_index_ref": "asset_index.json",
        "caption_safe_ref": "caption_safe.json",
        "ingest": {
            "pc_pack_path": "pc-pack",
            "size_caps_ok": True,
            "creators_session": "desk-session",
            "box_studio_only": False,
        },
        "distro_go": {"path": "distro-go.json"},
    }
    _dump(root / "manifest.json", manifest)
    return root
