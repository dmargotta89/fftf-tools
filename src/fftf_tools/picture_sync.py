"""fftf picture-sync — shot map, duck schedule, and sync check.

Duck rows come from the existing CLIP-NOTES / duck-cue parser. v1 pairs those
rows to VO beats in list order. It does not call out to the network.
Distro stays blocked.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fftf_tools.duck_sheet import ClipSection, DuckCue, parse_clip_sections, parse_duck_cues
from fftf_tools.schema import (
    Asset,
    ContractError,
    Fence,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    hold_tool_fences,
    load_json_value,
    normalize_episode_id,
    parse_assets,
    slugify,
    write_machine,
)

_URL = re.compile(r"https?://[^\s<>)\]]+")
_BEATS = (
    ("cold_open", re.compile(r"COLD\s+OPEN", re.I)),
    ("fiction", re.compile(r"FICTION", re.I)),
    ("pushback", re.compile(r"PUSHBACK", re.I)),
    ("reveal", re.compile(r"REVEAL", re.I)),
    ("aftermath", re.compile(r"AFTERMATH", re.I)),
)
_MIN_S = 8.0
_MAX_S = 20.0


def _episode_from_text(text: str) -> str | None:
    match = re.search(r"(?m)^Episode:\s*([A-Za-z0-9][A-Za-z0-9-]*)\s*$", text)
    if not match:
        return None
    return normalize_episode_id(match.group(1))


def _vo_sections(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("##"):
            continue
        for beat, pattern in _BEATS:
            if pattern.search(line):
                found.append((beat, line.lstrip("#").strip()))
                break
    return found


def _clean_url(url: str) -> str:
    return url.rstrip(".,;)")


def _infer_license(body: str) -> str:
    low = body.lower()
    if "public domain" in low or "pd-usgov" in low or re.search(r"\bpd\b", low):
        return "PD"
    if re.search(r"\bcia\b", low):
        return "cia"
    if any(token in low for token in ("nara", "national archives", "government")):
        return "gov"
    return "other"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _existing_file(path_str: str, notes_path: Path) -> Path | None:
    if not path_str:
        return None
    candidate = Path(path_str)
    if candidate.is_file():
        return candidate
    sibling = notes_path.parent / path_str
    if sibling.is_file():
        return sibling
    return None


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _sources_from_notes(sections: list[ClipSection], notes_text: str) -> list[Source]:
    sources: list[Source] = []
    seen: set[str] = set()
    for section in sections:
        for match in _URL.finditer(section.body):
            url = _clean_url(match.group(0))
            if url in seen or url not in notes_text:
                continue
            seen.add(url)
            sources.append(Source(n=len(sources) + 1, url=url, label=section.clip or "clip notes"))
    if not sources:
        for match in _URL.finditer(notes_text):
            url = _clean_url(match.group(0))
            if url in seen:
                continue
            seen.add(url)
            sources.append(Source(n=len(sources) + 1, url=url, label="URL cited in clip notes"))
    return sources


def _assets_from_sections(
    sections: list[ClipSection],
    ducks: list[dict],
    notes_path: Path,
) -> list[Asset]:
    beat_for_clip: dict[str, str] = {}
    for duck in ducks:
        beat_for_clip.setdefault(str(duck["clip"]), str(duck["beat"]))
    assets: list[Asset] = []
    seen: set[str] = set()
    for section in sections:
        path = section.source_path or section.clip
        if not path or path in seen:
            continue
        seen.add(path)
        on_disk = _existing_file(section.source_path, notes_path)
        assets.append(
            Asset(
                path=path,
                beat=beat_for_clip.get(section.clip, "cold_open"),
                license=_infer_license(section.body),
                sha256=_sha256(on_disk) if on_disk else "",
            )
        )
    return assets


def _pair_ducks(cues: list[DuckCue], sections: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    ducks: list[dict] = []
    flags: list[dict] = [
        {
            "level": "info",
            "code": "order-paired",
            "detail": "v1 assigns ducks to beats in list order. This is not a timecode lock. Pause VO under clip audio.",
        }
    ]
    if not cues:
        flags.append(
            {
                "level": "fail",
                "code": "no-ducks",
                "detail": "No duck cues were parsed from the clip notes.",
            }
        )
    for index, cue in enumerate(cues):
        if index < len(sections):
            beat, heading = sections[index]
            note = f"order-paired with {heading}"
        elif sections:
            beat, heading = sections[-1]
            note = f"extra duck after VO sections; beat repeats {heading}"
            flags.append(
                {
                    "level": "warn",
                    "code": "extra-duck",
                    "detail": f"{cue.clip} {cue.in_tc}–{cue.out_tc} has no unused VO section.",
                }
            )
        else:
            beat = "cold_open"
            note = "no VO section headings; beat defaults to cold_open"
            if index == 0:
                flags.append(
                    {
                        "level": "warn",
                        "code": "no-vo-sections",
                        "detail": "VO-timing has no Fiction / Pushback / Reveal / Aftermath / cold-open headings.",
                    }
                )
        if cue.duration_s < _MIN_S or cue.duration_s > _MAX_S:
            flags.append(
                {
                    "level": "warn",
                    "code": "duration-window",
                    "detail": (
                        f"{cue.clip} {cue.in_tc}–{cue.out_tc} is {cue.duration_s:.1f}s. "
                        f"Prefer about {_MIN_S:.0f}–{_MAX_S:.0f}s."
                    ),
                }
            )
        ducks.append(
            {
                "clip": cue.clip,
                "in": cue.in_tc,
                "out": cue.out_tc,
                "duration_s": cue.duration_s,
                "label": cue.label,
                "vo_pause_note": cue.vo_pause_note,
                "beat": beat,
                "source_path": cue.source_path,
                "pair_note": note,
            }
        )
    if len(sections) > len(cues):
        for beat, heading in sections[len(cues) :]:
            flags.append(
                {
                    "level": "warn",
                    "code": "section-without-duck",
                    "detail": f"{heading} ({beat}) has no duck in the v1 order pairing.",
                }
            )
    return ducks, flags


def _qc_gates(ducks: list[dict], flags: list[dict], vo_text: str, assets: list[Asset]) -> list[dict]:
    outliers = [flag for flag in flags if flag["code"] == "duration-window"]
    if not ducks:
        duration_status = "fail"
        duration_detail = "No ducks to measure."
    elif outliers:
        duration_status = "warn"
        duration_detail = f"{len(outliers)} duck(s) sit outside the 8–20s preference."
    else:
        duration_status = "pass"
        duration_detail = "Every parsed duck is inside 8–20s."
    has_pause = bool(re.search(r"\[p\]|\[P\]", vo_text))
    return [
        {
            "id": "distro-blocked",
            "status": "pass",
            "detail": "distro_blocked is true. Picture sync does not publish.",
        },
        {
            "id": "ducks-parsed",
            "status": "pass" if ducks else "fail",
            "detail": f"{len(ducks)} duck cue(s) parsed with the duck-sheet reader.",
        },
        {"id": "duck-duration-window", "status": duration_status, "detail": duration_detail},
        {
            "id": "vo-pause-markers",
            "status": "pass" if has_pause else "warn",
            "detail": "VO-timing contains [p] or [P]." if has_pause else "VO-timing has no [p] or [P] markers.",
        },
        {
            "id": "asset-index",
            "status": "pass" if assets else "warn",
            "detail": f"{len(assets)} asset(s) in the index." if assets else "Asset index is empty.",
        },
    ]


def _shot_map(episode_id: str, ducks: list[dict], sections: list[tuple[str, str]], cues_len: int) -> str:
    rows = [
        "| beat | vo_section | clip | in | out | duration_s | label | note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for duck in ducks:
        rows.append(
            "| "
            + " | ".join(
                [
                    _cell(duck["beat"]),
                    _cell(duck["pair_note"]),
                    _cell(duck["clip"]),
                    _cell(duck["in"]),
                    _cell(duck["out"]),
                    f"{duck['duration_s']:.1f}",
                    _cell(duck["label"]),
                    _cell(duck["vo_pause_note"]),
                ]
            )
            + " |"
        )
    if len(sections) > cues_len:
        for beat, heading in sections[cues_len:]:
            rows.append(f"| {beat} | {_cell(heading)} |  |  |  |  |  | no duck in v1 order pairing |")
    return "\n".join(
        [
            f"# Shot map — {episode_id}",
            "",
            channel_line(),
            "Distro: blocked. Pause VO under clip audio.",
            "",
            "v1 pairs ducks to beats in list order. Cut still locks picture to the VO.",
            "",
            *rows,
            "",
        ]
    )


def _check_md(episode_id: str, gates: list[dict], flags: list[dict]) -> str:
    gate_rows = ["| id | status | detail |", "|---|---|---|"]
    for gate in gates:
        gate_rows.append(
            f"| {gate['id']} | {gate['status']} | {_cell(gate['detail'])} |"
        )
    flag_lines = [
        f"- **{flag['level']}** `{flag['code']}`: {flag['detail']}" for flag in flags
    ] or ["- (none)"]
    return "\n".join(
        [
            f"# Picture sync check — {episode_id}",
            "",
            channel_line(),
            "Distro: blocked (`distro_blocked` is true). This check does not publish or call YouTube or Spotify.",
            "",
            "## QC gates",
            "",
            *gate_rows,
            "",
            "## Sync flags",
            "",
            *flag_lines,
            "",
            "## Notes",
            "",
            "- Duck rows are parsed by the same reader as `fftf duck-sheet`.",
            "- Prefer inserts of about 8–20 seconds. Shorter or longer rows are warnings, not a Distro unlock.",
            "- Pause VO under clip audio, then resume.",
            "",
        ]
    )


def run_picture_sync(
    vo_timing: Path | str,
    clip_notes: Path | str,
    assets_path: Path | str | None = None,
    out_dir: Path | str | None = None,
    episode_id: str | None = None,
) -> dict:
    vo_path = Path(vo_timing)
    notes_path = Path(clip_notes)
    if not vo_path.is_file():
        raise ContractError(f"VO-timing not found: {vo_path}")
    if not notes_path.is_file():
        raise ContractError(f"clip notes not found: {notes_path}")
    vo_text = vo_path.read_text(encoding="utf-8")
    notes_text = notes_path.read_text(encoding="utf-8")
    episode_id = normalize_episode_id(
        episode_id or _episode_from_text(vo_text) or slugify(vo_path.stem)
    )
    cues = parse_duck_cues(notes_path)
    sections = parse_clip_sections(notes_path)
    vo_sections = _vo_sections(vo_text)
    ducks, flags = _pair_ducks(cues, vo_sections)
    if assets_path:
        supplied = parse_assets(load_json_value(str(assets_path)))
        indexed = {Path(asset.path).stem for asset in supplied if asset.path}
        for cue in cues:
            stem = Path(cue.source_path).stem if cue.source_path else cue.clip
            if stem not in indexed and cue.clip not in indexed:
                flags.append(
                    {
                        "level": "warn",
                        "code": "duck-not-in-asset-index",
                        "detail": f"{cue.clip} is not in the supplied asset index.",
                    }
                )
        assets = supplied
    else:
        assets = _assets_from_sections(sections, ducks, notes_path)
    gates = _qc_gates(ducks, flags, vo_text, assets)
    sources = _sources_from_notes(sections, notes_text)
    for source in sources:
        if source.url not in notes_text:
            raise ContractError("picture-sync refused to emit a URL that is not in the clip notes")

    window_held = bool(cues) and all(_MIN_S <= cue.duration_s <= _MAX_S for cue in cues)
    fences = default_fences()
    hold_tool_fences(fences)
    for fence in fences:
        if fence.id in {"vocab-cartoon", "vocab-spine"}:
            # This command does not write narration, so it does not claim the vocab fence.
            fence.status = "unknown"
    fences.append(
        Fence(
            id="duck-window-8-20",
            rule="Prefer duck inserts of about 8 to 20 seconds.",
            status="held" if window_held else "unknown",
        )
    )

    out = Path(out_dir) if out_dir else Path(f"{episode_id}-picture")
    out.mkdir(parents=True, exist_ok=True)
    schedule = {
        "episode_id": episode_id,
        "distro_blocked": True,
        "ducks": ducks,
    }
    (out / "SHOT-MAP.md").write_text(
        _shot_map(episode_id, ducks, vo_sections, len(cues)),
        encoding="utf-8",
    )
    (out / "DUCK-SCHEDULE.json").write_text(
        json.dumps(schedule, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out / "PICTURE-SYNC-CHECK.md").write_text(
        _check_md(episode_id, gates, flags),
        encoding="utf-8",
    )
    public_ducks = []
    for duck in ducks:
        public_ducks.append(
            {
                "clip": duck["clip"],
                "in": duck["in"],
                "out": duck["out"],
                "duration_s": duck["duration_s"],
                "label": duck["label"],
                "vo_pause_note": duck["vo_pause_note"],
                "beat": duck["beat"],
            }
        )
    payload = contract_payload(
        episode_id,
        sources=sources,
        fences=fences,
        asset_index=assets,
        tool="picture-sync",
        ducks=public_ducks,
        sync_flags=flags,
        qc_gates=gates,
        outputs=[
            "SHOT-MAP.md",
            "DUCK-SCHEDULE.json",
            "PICTURE-SYNC-CHECK.md",
            f"{episode_id}.machine.json",
        ],
    )
    return write_machine(out / f"{episode_id}.machine.json", payload)
