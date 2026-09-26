"""Hard gates shared by Edit and Distro.

Bake and ``--apply`` refuse when any required gate fails. Codes are stable
machine blockers (``gate_script_unstamped``, ``gate_wording_hash_mismatch``, …).
Spoken VO and on-screen cards are never rewritten here.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from fftf_tools.channel_profile import (
    ALLOWED_LICENSES,
    CHANNEL_SLUG,
    CHROME_LOCK,
    DISPLAY_NAME,
    DISPLAY_NAME_SHORT,
    IG_FIT,
    IG_THUMB,
    YT_THUMB,
    checklist_row,
)
from fftf_tools.episode_pack import (
    AssetRec,
    Blocker,
    LoadedPack,
    episode_prefix,
    hash_path,
    md5_file,
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_WS = re.compile(r"\s+")


def norm_text(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def dedupe(blockers: list[Blocker]) -> list[Blocker]:
    seen: set[str] = set()
    out: list[Blocker] = []
    for blocker in blockers:
        if blocker.code in seen:
            continue
        seen.add(blocker.code)
        out.append(blocker)
    return out


def codes(blockers: list[Blocker]) -> list[str]:
    return [blocker.code for blocker in dedupe(blockers)]


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None


def approved_cards(caption: dict) -> list[dict]:
    """On-screen lines from caption_safe cards or Verifier-approved quote cards.

    Source Notes are not returned, even if a card copies them.
    """
    notes = norm_text(str(caption.get("notes") or ""))
    cards: list[dict] = []
    for card in caption.get("cards") or []:
        if not isinstance(card, dict):
            continue
        text = str(card.get("text") or "").strip()
        source = str(card.get("source") or "")
        if source != "caption_safe" or not text:
            continue
        if notes and norm_text(text) == notes:
            continue
        cards.append({"id": str(card.get("id") or ""), "text": text, "source": "caption_safe"})
    for card in caption.get("quote_cards") or []:
        if not isinstance(card, dict):
            continue
        text = str(card.get("text") or "").strip()
        if card.get("verifier_approved") is not True or not text:
            continue
        if notes and norm_text(text) == notes:
            continue
        cards.append({"id": str(card.get("id") or ""), "text": text, "source": "quote_card"})
    return cards


def _check_verdict(pack: LoadedPack, blockers: list[Blocker], *, allow_pwe: bool) -> None:
    if pack.verdict_path is None or not pack.verdict_path.is_file():
        blockers.append(Blocker("gate_verdict_missing", "Verifier verdict artifact is missing."))
        return
    if pack.review_path is None or not pack.review_path.is_file():
        blockers.append(Blocker("gate_verdict_missing", "Verifier review_path is missing."))
    status = str(pack.verdict.get("status") or "")
    allow = allow_pwe or pack.manifest.get("cos_allow_pwe") is True
    if status == "PASS":
        pass
    elif status in {"PWE", "PASS_WITH_EDITS"}:
        if not allow:
            blockers.append(
                Blocker("gate_verdict_pwe", "PWE does not allow bake unless CoS explicitly allows it.")
            )
    else:
        blockers.append(Blocker("gate_verdict_fail", f"Verifier status {status or 'missing'} does not allow bake."))
    if pack.verdict.get("claims_moved") is True or pack.manifest.get("claims_moved") is True:
        blockers.append(Blocker("gate_claims_moved", "Claims moved after the gate. Re-gate before bake."))
    pinned = str(pack.verdict.get("wording_hash") or "")
    flag = str(pack.verdict.get("match_vs_narration") or "")
    if flag != "MATCH" or not pack.narration_text or pinned != pack.wording_hash or not _HEX64.fullmatch(pinned):
        blockers.append(
            Blocker(
                "gate_wording_hash_mismatch",
                "Wording hash is not MATCH against narration-only.",
            )
        )
    try:
        pinned_count = int(pack.verdict.get("spoken_word_count"))
    except (TypeError, ValueError):
        pinned_count = -1
    if pinned_count != pack.spoken_word_count:
        blockers.append(
            Blocker("gate_spoken_word_count", "Pinned spoken-word count does not match narration-only.")
        )


def _check_stamps_and_thumbs(pack: LoadedPack, blockers: list[Blocker]) -> None:
    stamps = pack.stamps
    if stamps.get("script_stamped") is not True or stamps.get("script_stamped_by") != "Daniel":
        blockers.append(Blocker("gate_script_unstamped", "Daniel script stamp is required before bake."))
    vo_meta = pack.manifest.get("vo") if isinstance(pack.manifest.get("vo"), dict) else {}
    if vo_meta.get("rewritten_after_stamp") is True or vo_meta.get("immutable") is False:
        blockers.append(Blocker("gate_vo_rewritten", "Spoken VO was marked rewritten after stamp."))
    if stamps.get("soft_parked") is True:
        blockers.append(Blocker("gate_thumb_soft_parked", "Soft-parked thumb options cannot ship."))

    prefix = episode_prefix(pack.episode_id)
    yt_rel = str(stamps.get("thumb_yt_path") or "")
    ig_rel = str(stamps.get("thumb_ig_path") or "")
    yt = pack.path(yt_rel)
    ig = pack.path(ig_rel)
    yt_name = Path(yt_rel).name
    ig_name = Path(ig_rel).name
    live_name = re.compile(rf"^{re.escape(prefix)}-.+-LIVE\.png$")
    ig_name_re = re.compile(rf"^{re.escape(prefix)}-.+-LIVE-ig45\.png$")
    if stamps.get("thumb_live") is not True or yt is None or not yt.is_file() or ig is None or not ig.is_file():
        blockers.append(Blocker("gate_thumb_live_missing", "Frame LIVE YT and IG paths must both be present."))
        return
    if not live_name.match(yt_name) or not ig_name_re.match(ig_name):
        blockers.append(Blocker("gate_thumb_not_live", "Thumbs must be LIVE aliases for this episode_id."))
    if stamps.get("thumb_ig_fit") != IG_FIT:
        blockers.append(Blocker("gate_ig_stretch", "IG thumb must be CONTAIN+pad, never stretch."))
    yt_size = _image_size(yt)
    ig_size = _image_size(ig)
    if yt_size != YT_THUMB or ig_size != IG_THUMB:
        blockers.append(
            Blocker(
                "gate_live_thumb_size",
                f"LIVE sizes must be YT {YT_THUMB[0]}×{YT_THUMB[1]} and IG {IG_THUMB[0]}×{IG_THUMB[1]}.",
            )
        )
    fixed = str(stamps.get("thumb_fixed_sha256") or "")
    try:
        yt_sha = hash_path(yt)
    except FileNotFoundError:
        yt_sha = ""
    if not _HEX64.fullmatch(fixed) or fixed != yt_sha:
        blockers.append(Blocker("gate_live_hash_mismatch", "FIXED hash is not byte-identical to the YT LIVE file."))
    ig_fixed = stamps.get("thumb_ig_sha256")
    if isinstance(ig_fixed, str) and ig_fixed:
        try:
            ig_sha = hash_path(ig)
        except FileNotFoundError:
            ig_sha = ""
        if ig_fixed != ig_sha:
            blockers.append(Blocker("gate_live_hash_mismatch", "IG LIVE hash does not match the file."))
    md5 = str(stamps.get("thumb_md5") or stamps.get("md5") or "")
    if not md5 or md5 != md5_file(yt):
        blockers.append(Blocker("gate_thumb_brief_missing", "Thumb brief md5 does not match the YT LIVE file."))
    if not str(stamps.get("hook_text") or "").strip() or not str(stamps.get("opt_letter") or "").strip():
        blockers.append(Blocker("gate_thumb_brief_missing", "Thumb brief needs hook text and opt letter."))
    chrome = stamps.get("chrome_lock")
    if not isinstance(chrome, dict) or any(chrome.get(key) != value for key, value in CHROME_LOCK.items()):
        blockers.append(
            Blocker(
                "gate_chrome_lock",
                "Chrome lock is Liberation Sans Bold, drip 0, full yellow underline, FFTF badge, EPISODE pill.",
            )
        )


def _check_caption(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if not pack.caption:
        blockers.append(Blocker("gate_caption_safe_missing", "caption_safe artifact is missing."))
        return
    notes = str(pack.caption.get("notes") or "")
    if "notes" not in pack.caption:
        blockers.append(Blocker("gate_caption_safe_missing", "caption_safe must carry a notes field distinct from cards."))
    notes_norm = norm_text(notes)
    saw_card = False
    for card in pack.caption.get("cards") or []:
        if not isinstance(card, dict):
            continue
        saw_card = True
        source = str(card.get("source") or "")
        text = str(card.get("text") or "")
        if source in {"notes", "source_notes", "note"}:
            blockers.append(Blocker("gate_caption_safe_equals_notes", "Lower-thirds cannot use Source Notes."))
        elif source != "caption_safe":
            blockers.append(Blocker("gate_caption_from_notes", "Lower-thirds must use caption_safe or a quote card."))
        if notes_norm and norm_text(text) == notes_norm:
            blockers.append(Blocker("gate_caption_safe_equals_notes", "caption_safe text equals Source Notes."))
    for card in pack.caption.get("quote_cards") or []:
        if not isinstance(card, dict):
            continue
        saw_card = True
        text = str(card.get("text") or "")
        if card.get("verifier_approved") is not True:
            blockers.append(Blocker("gate_caption_from_notes", "Quote cards must be Verifier-approved."))
        if notes_norm and norm_text(text) == notes_norm:
            blockers.append(Blocker("gate_caption_safe_equals_notes", "Quote card text equals Source Notes."))
    if not saw_card:
        blockers.append(Blocker("gate_caption_safe_missing", "caption_safe has no cards."))


def _referenced_ids(pack: LoadedPack) -> set[str]:
    wanted: set[str] = set()
    for source in pack.sources:
        asset_id = str(source.get("asset_id") or source.get("id") or "")
        if asset_id:
            wanted.add(asset_id)
    for beat in pack.timeline:
        for broll in beat.get("broll") or []:
            if isinstance(broll, dict) and broll.get("asset_id"):
                wanted.add(str(broll["asset_id"]))
    return wanted


def _check_assets(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if not pack.assets:
        blockers.append(Blocker("gate_license_missing", "asset_index is missing."))
        return
    by_id = {asset.asset_id: asset for asset in pack.assets if asset.asset_id}
    for asset_id in sorted(_referenced_ids(pack)):
        if asset_id not in by_id:
            blockers.append(Blocker("gate_asset_missing", f"{asset_id} is not in asset_index."))
    for asset in pack.assets:
        _check_one_asset(asset, blockers)


def _check_one_asset(asset: AssetRec, blockers: list[Blocker]) -> None:
    if asset.path is None or not asset.path.exists():
        blockers.append(Blocker("gate_asset_missing", f"{asset.asset_id or asset.rel} path is missing."))
        return
    if not asset.license.strip():
        blockers.append(Blocker("gate_license_missing", f"{asset.asset_id or asset.rel} has no license."))
    elif asset.license not in ALLOWED_LICENSES:
        blockers.append(Blocker("gate_license_invalid", f"{asset.asset_id or asset.rel} license is not allowed."))
    if not asset.sha256.strip():
        blockers.append(Blocker("gate_sha_missing", f"{asset.asset_id or asset.rel} has no SHA-256."))
        return
    try:
        actual = hash_path(asset.path)
    except FileNotFoundError:
        blockers.append(Blocker("gate_asset_missing", f"{asset.asset_id or asset.rel} path is missing."))
        return
    if actual != asset.sha256:
        blockers.append(Blocker("gate_sha_mismatch", f"{asset.asset_id or asset.rel} SHA-256 does not match."))


def _check_display(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if pack.display_name != DISPLAY_NAME or pack.display_short != DISPLAY_NAME_SHORT or pack.channel_slug != CHANNEL_SLUG:
        blockers.append(
            Blocker("gate_display_name", "Display name lock is From Fiction to Fact / FFTF only.")
        )


def _check_vo_file(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if pack.narration_path is None or not pack.narration_path.is_file() or not pack.narration_text.strip():
        blockers.append(Blocker("missing_vo", "Narration-only file is missing."))
    if pack.vo_path is None or not pack.vo_path.is_file():
        blockers.append(Blocker("missing_vo", "VO stem is missing."))


def edit_blockers(pack: LoadedPack, *, allow_pwe: bool = False) -> list[Blocker]:
    """Gates that refuse an edit bake. Picture QC and publish are not this stage."""
    blockers = list(pack.load_errors)
    _check_display(pack, blockers)
    _check_vo_file(pack, blockers)
    _check_verdict(pack, blockers, allow_pwe=allow_pwe)
    _check_stamps_and_thumbs(pack, blockers)
    _check_caption(pack, blockers)
    _check_assets(pack, blockers)
    return dedupe(blockers)


def _master_file(pack: LoadedPack, node: object) -> tuple[Path | None, str]:
    if not isinstance(node, dict):
        return None, ""
    return pack.path(node.get("path")), str(node.get("sha256") or "")


def _check_master(pack: LoadedPack, node: object, label: str, blockers: list[Blocker]) -> None:
    path, pinned = _master_file(pack, node)
    if path is None or not path.is_file():
        blockers.append(Blocker("gate_master_missing", f"{label} master is missing."))
        return
    if not pinned:
        blockers.append(Blocker("gate_master_hash_mismatch", f"{label} master has no SHA-256."))
        return
    if hash_path(path) != pinned:
        blockers.append(Blocker("gate_master_hash_mismatch", f"{label} master SHA-256 does not match."))


def _check_meta(pack: LoadedPack, blockers: list[Blocker]) -> None:
    meta = pack.meta
    inherits = meta.get("inherits_locked_narration") is True
    gated = meta.get("claim_gated") is True
    if not inherits and not gated:
        blockers.append(Blocker("gate_meta_ungated", "Distro meta must inherit locked narration or be claim-gated."))
    notes = norm_text(str(pack.caption.get("notes") or ""))
    fields = [str(meta.get("title") or ""), str(meta.get("description") or "")]
    hooks = meta.get("shorts_hooks") if isinstance(meta.get("shorts_hooks"), dict) else {}
    for letter in ("A", "B", "C", "D"):
        hook = str(hooks.get(letter) or "")
        fields.append(hook)
        if not hook.strip():
            blockers.append(Blocker("gate_shorts_hooks", f"Shorts hook {letter} is empty."))
    if notes:
        for field in fields:
            if field.strip() and norm_text(field) == notes:
                blockers.append(Blocker("gate_meta_ungated", "Distro meta copies Source Notes."))
                break
    if inherits:
        listed = [str(item) for item in meta.get("sources_list") or []]
        if listed != pack.approved_sources:
            blockers.append(
                Blocker("gate_sources_not_verbatim", "sources_list is not the approved Sources list verbatim.")
            )
        description = str(meta.get("description") or "")
        for source in pack.approved_sources:
            if source not in description:
                blockers.append(
                    Blocker("gate_sources_not_verbatim", "Description omits an approved source.")
                )
                break
    if not str(meta.get("title") or "").strip():
        blockers.append(Blocker("gate_meta_ungated", "Distro title is empty."))


def _check_picture_qc(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if pack.picture_qc.get("passed") is not True:
        blockers.append(Blocker("gate_picture_qc", "Picture QC has not passed."))
        return
    note = pack.path(pack.picture_qc.get("note_path"))
    if note is None or not note.is_file() or not note.read_text(encoding="utf-8").strip():
        blockers.append(Blocker("gate_picture_qc", "Picture QC note is missing."))


def _check_ingest(pack: LoadedPack, blockers: list[Blocker]) -> None:
    if pack.ingest.get("box_studio_only") is True:
        blockers.append(Blocker("gate_ingest_box_only", "Box Studio drag cannot be the only ingest path."))
    pc = pack.path(pack.ingest.get("pc_pack_path"))
    creators = str(pack.ingest.get("creators_session") or "").strip()
    if pc is None and not creators:
        blockers.append(Blocker("gate_ingest_pc_pack", "PC pack path or a Creators session is required."))
    elif pc is not None and not pc.exists():
        blockers.append(Blocker("gate_ingest_pc_pack", "PC pack path does not exist."))


def iter_size_rows(pack: LoadedPack) -> list[dict]:
    """PC-pack size checklist. Upload stays manual; this only measures local files."""
    masters = pack.masters if isinstance(pack.masters, dict) else {}
    rows = [
        checklist_row("yt_long", pack.path((masters.get("longform") or {}).get("path") if isinstance(masters.get("longform"), dict) else None), "yt_long"),
        checklist_row("podcast_audio", pack.path((masters.get("podcast_yt_length") or {}).get("path") if isinstance(masters.get("podcast_yt_length"), dict) else None), "podcast_audio"),
        checklist_row("cover", pack.path(pack.cover.get("path")), "cover"),
        checklist_row("thumb_yt", pack.path(pack.stamps.get("thumb_yt_path")), "thumb"),
        checklist_row("thumb_ig", pack.path(pack.stamps.get("thumb_ig_path")), "thumb"),
    ]
    shorts = masters.get("shorts") if isinstance(masters.get("shorts"), list) else []
    by_letter = {str(item.get("id")): item for item in shorts if isinstance(item, dict)}
    for letter in ("A", "B", "C", "D"):
        node = by_letter.get(letter) or {}
        rows.append(checklist_row(f"short_{letter}", pack.path(node.get("path")), "short"))
    extended = masters.get("podcast_extended") if isinstance(masters.get("podcast_extended"), dict) else {}
    if extended.get("path"):
        rows.append(checklist_row("podcast_extended", pack.path(extended.get("path")), "podcast_extended"))
    return rows


def _check_sizes(pack: LoadedPack, blockers: list[Blocker]) -> None:
    for row in iter_size_rows(pack):
        if row["bytes"] is not None and row["ok"] is False:
            blockers.append(Blocker("gate_size_cap", f"{row['id']} exceeds the channel size cap."))


def _check_go(pack: LoadedPack, blockers: list[Blocker]) -> None:
    go = pack.distro_go
    if (
        not isinstance(go, dict)
        or go.get("approved") is not True
        or go.get("kind") != "distro"
        or go.get("episode_id") != pack.episode_id
        or go.get("approved_by") != "Distro"
    ):
        blockers.append(Blocker("gate_distro_go", "Distro GO is required before apply. This wave still does not upload."))


def distro_blockers(pack: LoadedPack, *, allow_pwe: bool = False) -> list[Blocker]:
    """Content gates plus frozen-assembly gates. Does not publish."""
    blockers = edit_blockers(pack, allow_pwe=allow_pwe)
    _check_picture_qc(pack, blockers)
    _check_meta(pack, blockers)
    masters = pack.masters
    _check_master(pack, masters.get("longform"), "long-form", blockers)
    shorts = masters.get("shorts") if isinstance(masters.get("shorts"), list) else []
    by_letter = {str(item.get("id")): item for item in shorts if isinstance(item, dict)}
    for letter in ("A", "B", "C", "D"):
        _check_master(pack, by_letter.get(letter), f"short {letter}", blockers)
    _check_master(pack, masters.get("podcast_yt_length"), "podcast YT-length", blockers)
    _check_ingest(pack, blockers)
    _check_sizes(pack, blockers)
    _check_go(pack, blockers)
    return dedupe(blockers)


def valid_longform_url(url: str | None) -> bool:
    if not url or "{{" in url or " " in url:
        return False
    if not url.startswith("https://"):
        return False
    rest = url[len("https://") :]
    return bool(rest) and "." in rest.split("/")[0]


def load_go_file(path: Path | None, *, kind: str, episode_id: str) -> dict | None:
    if path is None or not path.is_file():
        return None
    try:
        data = read_json_dict(path)
    except (OSError, ValueError):
        return None
    if (
        data.get("approved") is True
        and data.get("kind") == kind
        and data.get("episode_id") == episode_id
        and data.get("approved_by") == "Distro"
    ):
        return data
    return None


def read_json_dict(path: Path) -> dict:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GO artifact must be a JSON object")
    return data


def shorts_blockers(pack: LoadedPack, longform_url: str | None, *, allow_pwe: bool = False) -> list[Blocker]:
    blockers = distro_blockers(pack, allow_pwe=allow_pwe)
    if not valid_longform_url(longform_url):
        blockers.append(
            Blocker("gate_shorts_longform_url", "Shorts run after yt-long and require an https long-form URL.")
        )
    return dedupe(blockers)


def _cover_ok(pack: LoadedPack) -> bool:
    if pack.cover.get("locked") is not True:
        return False
    path = pack.path(pack.cover.get("path"))
    pinned = str(pack.cover.get("sha256") or "")
    if path is None or not path.is_file() or not pinned:
        return False
    return hash_path(path) == pinned


def podcast_blockers(pack: LoadedPack, *, allow_pwe: bool = False) -> list[Blocker]:
    blockers = distro_blockers(pack, allow_pwe=allow_pwe)
    if not _cover_ok(pack):
        blockers.append(Blocker("gate_cover_unlocked", "Podcast cover must be LOCKED and hash-matched."))
    return dedupe(blockers)


def podcast_extended_blockers(
    pack: LoadedPack,
    go_path: Path | None,
    *,
    allow_pwe: bool = False,
) -> list[Blocker]:
    """Extended audio is not part of the YT wave. It needs its own GO."""
    blockers = distro_blockers(pack, allow_pwe=allow_pwe)
    node = pack.masters.get("podcast_extended") if isinstance(pack.masters.get("podcast_extended"), dict) else {}
    _check_master(pack, node, "podcast extended", blockers)
    go = load_go_file(go_path, kind="podcast_extended", episode_id=pack.episode_id)
    if go is None:
        manifest_go = pack.path(node.get("go_path") if isinstance(node, dict) else None)
        go = load_go_file(manifest_go, kind="podcast_extended", episode_id=pack.episode_id)
    if go is None:
        blockers.append(
            Blocker("gate_podcast_extended_go", "podcast-extended requires a separate Distro GO.")
        )
    return dedupe(blockers)


# Gate matrix rows for the status report. Order matches the stamped hard-gate list.
GATE_MATRIX: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("verdict", "Verifier verdict pin", frozenset({"gate_verdict_missing", "gate_verdict_fail", "gate_verdict_pwe", "gate_spoken_word_count"})),
    ("wording", "Wording hash MATCH / claims freeze", frozenset({"gate_wording_hash_mismatch", "gate_claims_moved", "gate_vo_rewritten"})),
    ("dual_stamp", "Daniel script stamp + thumb LIVE", frozenset({"gate_script_unstamped", "gate_thumb_live_missing"})),
    ("thumbs", "LIVE-only thumbs, FIXED hash, chrome, CONTAIN+pad", frozenset({"gate_thumb_not_live", "gate_live_hash_mismatch", "gate_live_thumb_size", "gate_ig_stretch", "gate_chrome_lock", "gate_thumb_soft_parked", "gate_thumb_brief_missing"})),
    ("caption_safe", "caption_safe distinct from Source Notes", frozenset({"gate_caption_safe_missing", "gate_caption_safe_equals_notes", "gate_caption_from_notes"})),
    ("asset_index", "license + SHA on shipped assets", frozenset({"gate_license_missing", "gate_license_invalid", "gate_sha_missing", "gate_sha_mismatch", "gate_asset_missing"})),
    ("picture_qc", "Picture QC note", frozenset({"gate_picture_qc"})),
    ("display_name", "From Fiction to Fact / FFTF", frozenset({"gate_display_name"})),
    ("meta", "Claim-gated Distro meta", frozenset({"gate_meta_ungated", "gate_sources_not_verbatim", "gate_shorts_hooks"})),
    ("masters", "Frozen masters and hashes", frozenset({"gate_master_missing", "gate_master_hash_mismatch"})),
    ("ingest", "PC pack / size caps / not box-only", frozenset({"gate_ingest_pc_pack", "gate_ingest_box_only", "gate_size_cap"})),
    ("authority", "Distro GO (live upload stays blocked)", frozenset({"gate_distro_go"})),
)


def gate_matrix(blockers: list[Blocker]) -> list[dict]:
    failed = {blocker.code for blocker in blockers}
    rows = []
    for gate_id, label, codes_for_gate in GATE_MATRIX:
        hit = sorted(failed & codes_for_gate)
        rows.append(
            {
                "id": gate_id,
                "label": label,
                "ok": not hit,
                "blockers": hit,
            }
        )
    return rows
