"""Load an assembled episode pack from disk.

Paths may be relative to the pack root or absolute, as Cut emitted them.
This module only reads. It does not rewrite VO, cards, or thumbs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_WORD = re.compile(r"[A-Za-z0-9']+")
_EP_PREFIX = re.compile(r"^(ep\d+)", re.IGNORECASE)


def spoken_words(text: str) -> list[str]:
    """Narration-only tokens. Pause markers such as ``[p]`` are not words."""
    return _WORD.findall(text.lower())


def wording_hash(text: str) -> str:
    """SHA-256 of the spoken-word sequence. Used as the Verifier wording pin."""
    payload = " ".join(spoken_words(text)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def spoken_word_count(text: str) -> int:
    return len(spoken_words(text))


def hash_path(path: Path) -> str:
    """SHA-256 of a file, or of a directory's sorted files (relative name + bytes)."""
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        for item in files:
            rel = item.relative_to(path).as_posix().encode("utf-8")
            digest.update(rel)
            digest.update(b"\0")
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            digest.update(b"\0")
        return digest.hexdigest()
    raise FileNotFoundError(path)


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def episode_prefix(episode_id: str) -> str:
    match = _EP_PREFIX.match(episode_id.strip())
    if match:
        return match.group(1).lower()
    return episode_id.strip().lower()


def resolve_pack_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Blocker:
    code: str
    detail: str


@dataclass
class AssetRec:
    asset_id: str
    rel: str
    path: Path | None
    role: str
    license: str
    sha256: str
    type: str


@dataclass
class LoadedPack:
    root: Path
    manifest: dict
    episode_id: str
    display_name: str
    display_short: str
    channel_slug: str
    title: str
    narration_text: str
    narration_path: Path | None
    vo_path: Path | None
    wording_hash: str
    spoken_word_count: int
    verdict: dict
    verdict_path: Path | None
    review_path: Path | None
    stamps: dict
    caption: dict
    assets: list[AssetRec] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    edit: dict = field(default_factory=dict)
    picture_qc: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    approved_sources: list[str] = field(default_factory=list)
    ingest: dict = field(default_factory=dict)
    masters: dict = field(default_factory=dict)
    cover: dict = field(default_factory=dict)
    distro_go: dict | None = None
    music_enabled: bool = False
    load_errors: list[Blocker] = field(default_factory=list)

    def path(self, value: object) -> Path | None:
        return resolve_pack_path(self.root, value)


def _empty(root: Path, detail: str) -> LoadedPack:
    return LoadedPack(
        root=root,
        manifest={},
        episode_id="unknown",
        display_name="",
        display_short="",
        channel_slug="",
        title="",
        narration_text="",
        narration_path=None,
        vo_path=None,
        wording_hash="",
        spoken_word_count=0,
        verdict={},
        verdict_path=None,
        review_path=None,
        stamps={},
        caption={},
        load_errors=[Blocker("gate_pack_invalid", detail)],
    )


def _load_mapping(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def _asset_id(raw: dict) -> str:
    return str(raw.get("asset_id") or raw.get("id") or "").strip()


def load_pack(pack: Path | str) -> LoadedPack:
    """Read ``manifest.json`` (or a manifest file path). Missing pieces are errors, not guesses."""
    given = Path(pack)
    if given.is_dir():
        root = given
        manifest_path = root / "manifest.json"
    else:
        manifest_path = given
        root = given.parent
    if not manifest_path.is_file():
        return _empty(root, f"manifest not found: {manifest_path}")
    try:
        manifest = read_json(manifest_path)
    except json.JSONDecodeError as exc:
        return _empty(root, f"manifest is not JSON: {exc}")
    if not isinstance(manifest, dict):
        return _empty(root, "manifest must be a JSON object")

    episode_id = str(manifest.get("episode_id") or "").strip() or "unknown"
    vo = manifest.get("vo") if isinstance(manifest.get("vo"), dict) else {}
    narration_path = resolve_pack_path(root, vo.get("narration_path"))
    narration_text = ""
    if narration_path is not None and narration_path.is_file():
        narration_text = narration_path.read_text(encoding="utf-8")
    vo_path = resolve_pack_path(root, vo.get("path"))

    verdict_inline = manifest.get("verdict") if isinstance(manifest.get("verdict"), dict) else {}
    verdict_path = resolve_pack_path(root, verdict_inline.get("path"))
    verdict = dict(verdict_inline)
    if verdict_path is not None and verdict_path.is_file():
        try:
            loaded = read_json(verdict_path)
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            verdict = loaded
            verdict.setdefault("path", verdict_inline.get("path"))
    review_path = resolve_pack_path(root, verdict.get("review_path"))

    caption_path = resolve_pack_path(root, manifest.get("caption_safe_ref"))
    caption = _load_mapping(caption_path)

    index_path = resolve_pack_path(root, manifest.get("asset_index_ref"))
    index_raw: object = []
    if index_path is not None and index_path.is_file():
        try:
            index_raw = read_json(index_path)
        except json.JSONDecodeError:
            index_raw = []
    if isinstance(index_raw, dict):
        rows = index_raw.get("assets") or index_raw.get("asset_index") or []
    elif isinstance(index_raw, list):
        rows = index_raw
    else:
        rows = []
    assets: list[AssetRec] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        assets.append(
            AssetRec(
                asset_id=_asset_id(row),
                rel=rel,
                path=resolve_pack_path(root, rel),
                role=str(row.get("role") or ""),
                license=str(row.get("license") or ""),
                sha256=str(row.get("sha256") or ""),
                type=str(row.get("type") or ""),
            )
        )

    go_path = None
    go_inline = manifest.get("distro_go")
    if isinstance(go_inline, dict):
        go_path = resolve_pack_path(root, go_inline.get("path"))
    elif isinstance(go_inline, str):
        go_path = resolve_pack_path(root, go_inline)
    distro_go = None
    if go_path is not None and go_path.is_file():
        try:
            loaded_go = read_json(go_path)
        except json.JSONDecodeError:
            loaded_go = None
        if isinstance(loaded_go, dict):
            distro_go = loaded_go

    music = manifest.get("music") if isinstance(manifest.get("music"), dict) else {}
    edit = manifest.get("edit") if isinstance(manifest.get("edit"), dict) else {}
    approved = manifest.get("approved_sources")
    if not isinstance(approved, list):
        approved = []

    return LoadedPack(
        root=root,
        manifest=manifest,
        episode_id=episode_id,
        display_name=str(manifest.get("display_name_lock") or manifest.get("display_name") or ""),
        display_short=str(manifest.get("display_name_short") or ""),
        channel_slug=str(manifest.get("channel") or ""),
        title=str(manifest.get("title") or ""),
        narration_text=narration_text,
        narration_path=narration_path,
        vo_path=vo_path,
        wording_hash=wording_hash(narration_text) if narration_text else "",
        spoken_word_count=spoken_word_count(narration_text) if narration_text else 0,
        verdict=verdict,
        verdict_path=verdict_path,
        review_path=review_path,
        stamps=manifest.get("stamps") if isinstance(manifest.get("stamps"), dict) else {},
        caption=caption,
        assets=assets,
        sources=[item for item in manifest.get("sources") or [] if isinstance(item, dict)],
        timeline=[item for item in manifest.get("timeline") or [] if isinstance(item, dict)],
        edit=edit,
        picture_qc=manifest.get("picture_qc") if isinstance(manifest.get("picture_qc"), dict) else {},
        meta=manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {},
        approved_sources=[str(item) for item in approved],
        ingest=manifest.get("ingest") if isinstance(manifest.get("ingest"), dict) else {},
        masters=manifest.get("masters") if isinstance(manifest.get("masters"), dict) else {},
        cover=manifest.get("cover") if isinstance(manifest.get("cover"), dict) else {},
        distro_go=distro_go,
        music_enabled=bool(music.get("enabled")),
    )
