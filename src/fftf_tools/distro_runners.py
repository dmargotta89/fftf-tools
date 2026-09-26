"""fftf distro — readiness and ordered publish runners.

``status`` never publishes. ``yt-long``, ``shorts``, ``podcast``, and
``podcast-extended`` are dry-run by default. ``--apply`` writes a local plan
and a room report. It does not call YouTube or Spotify. ``distro_blocked``
stays true.

Order is yt-long, then shorts (long-form URL required), then podcast with a
LOCKED cover. Podcast-extended is a separate GO and is not part of that wave.

Script, Verifier, and Frame do not import this module.

Specs stamped 2026-09-26: Distro utility plan v1 and the toolkit team input.
"""

from __future__ import annotations

from pathlib import Path

from fftf_tools.channel_profile import (
    DISPLAY_NAME,
    DISPLAY_NAME_SHORT,
    ORDERED_WAVES,
    SEPARATE_WAVES,
)
from fftf_tools.episode_pack import Blocker, LoadedPack, load_pack
from fftf_tools.gates import (
    codes,
    distro_blockers,
    gate_matrix,
    iter_size_rows,
    podcast_blockers,
    podcast_extended_blockers,
    shorts_blockers,
)
from fftf_tools.schema import (
    Asset,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    hold_tool_fences,
    write_machine,
)

_NO_LIVE = {
    "distro_blocked": True,
    "published": False,
    "uploads": False,
    "spend": False,
}


def _write_json(path: Path, payload: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _machine(pack: LoadedPack, out: Path, outputs: list[str], tool_blockers: list[str], tool: str) -> dict:
    fences = default_fences()
    hold_tool_fences(fences)
    sources = [
        Source(n=index, url="PLACEHOLDER", label=label[:240] or "approved source")
        for index, label in enumerate(pack.approved_sources, start=1)
    ]
    assets: list[Asset] = []
    for asset in pack.assets:
        if asset.license in {"PD", "gov", "cia", "other"}:
            assets.append(
                Asset(
                    path=asset.rel or "",
                    role=asset.role or asset.asset_id or "asset",
                    license=asset.license,
                    sha256=asset.sha256,
                )
            )
        else:
            assets.append(Asset(path=asset.rel or "", role=asset.role or "asset"))
    for name in outputs:
        assets.append(Asset(path=name, role="distro-output"))
    payload = contract_payload(
        pack.episode_id,
        sources=sources,
        fences=fences,
        asset_index=assets,
        tool=tool,
        channel=DISPLAY_NAME,
        channel_short=DISPLAY_NAME_SHORT,
        uploads=False,
        published=False,
        blockers=tool_blockers,
        outputs=outputs,
    )
    return write_machine(out / f"{pack.episode_id}.machine.json", payload)


def _thumb_report(pack: LoadedPack) -> dict:
    yt = pack.path(pack.stamps.get("thumb_yt_path"))
    ig = pack.path(pack.stamps.get("thumb_ig_path"))
    return {
        "episode_id": pack.episode_id,
        "yt_path": str(yt) if yt else None,
        "ig_path": str(ig) if ig else None,
        "fixed_sha256": pack.stamps.get("thumb_fixed_sha256"),
        "hook_text": pack.stamps.get("hook_text"),
        "opt_letter": pack.stamps.get("opt_letter"),
        "md5": pack.stamps.get("thumb_md5") or pack.stamps.get("md5"),
        "ig_fit": pack.stamps.get("thumb_ig_fit"),
        "chrome_lock": pack.stamps.get("chrome_lock"),
    }


def _runner_view(pack: LoadedPack, *, longform_url: str | None, extended_go: Path | None) -> dict:
    shared = codes(distro_blockers(pack))
    shorts_only = [code for code in codes(shorts_blockers(pack, longform_url)) if code not in shared]
    podcast_only = [code for code in codes(podcast_blockers(pack)) if code not in shared]
    extended_specific = [
        code
        for code in codes(podcast_extended_blockers(pack, extended_go))
        if code in {"gate_podcast_extended_go"} or (
            code in {"gate_master_missing", "gate_master_hash_mismatch"} and code not in shared
        )
    ]
    waiting = []
    if "gate_shorts_longform_url" in shorts_only:
        waiting.append("gate_shorts_longform_url")
    return {
        "yt-long": {"ready": not shared, "blockers": shared, "waiting": []},
        "shorts": {
            "ready": not shared and not shorts_only,
            "blockers": [code for code in shorts_only if code not in waiting],
            "waiting": waiting,
        },
        "podcast": {"ready": not shared and not podcast_only, "blockers": podcast_only, "waiting": []},
        "podcast-extended": {
            "ready": not shared and not extended_specific,
            "blockers": extended_specific,
            "waiting": [],
            "separate_go": True,
        },
    }


def _status_md(report: dict) -> str:
    lines = [
        f"# Distro status — {report['episode_id']}",
        "",
        channel_line(),
        "This report does not publish. Live YouTube and Spotify stay closed.",
        "distro_blocked: true",
        "",
        f"- Display name lock: {DISPLAY_NAME} ({DISPLAY_NAME_SHORT})",
        f"- Pack display name: {report.get('pack_display_name')}",
        "",
        "## Gate matrix",
        "",
        "| gate | ok | blockers |",
        "|---|---|---|",
    ]
    for row in report["gates"]:
        blockers = ", ".join(row["blockers"]) or "—"
        lines.append(f"| {row['id']} | {str(row['ok']).lower()} | {blockers} |")
    lines.extend(["", "## Ordered wave", ""])
    lines.append(" → ".join(report["ordered_waves"]))
    lines.append("")
    lines.append("Podcast-extended is not in this wave. It needs a separate GO.")
    lines.extend(["", "## Runners", ""])
    for name, view in report["runners"].items():
        lines.append(
            f"- `{name}` ready={str(view['ready']).lower()} "
            f"blockers={view['blockers'] or '—'} waiting={view.get('waiting') or '—'}"
        )
    lines.extend(["", "## Ingest and size caps", ""])
    ingest = report["ingest"]
    lines.append(f"- PC pack: {ingest.get('pc_pack_path')}")
    lines.append(f"- Creators session: {ingest.get('creators_session')}")
    lines.append(f"- Box Studio only: {str(ingest.get('box_studio_only')).lower()}")
    lines.append(f"- Size caps ok: {str(ingest.get('size_caps_ok')).lower()}")
    lines.extend(["", "| id | bytes | cap | ok |", "|---|---|---|---|"])
    for row in ingest["checklist"]:
        lines.append(f"| {row['id']} | {row['bytes']} | {row['cap_bytes']} | {str(row['ok']).lower()} |")
    lines.extend(["", "## Blockers", ""])
    if report["blockers"]:
        for code in report["blockers"]:
            lines.append(f"- `{code}`")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def _base_report(pack: LoadedPack, blockers: list[Blocker], *, longform_url: str | None, extended_go: Path | None) -> dict:
    rows = iter_size_rows(pack)
    pc = pack.path(pack.ingest.get("pc_pack_path"))
    size_ok = all(row["ok"] for row in rows if row["id"] != "podcast_extended")
    present = [row for row in rows if row["bytes"] is not None and row["id"] != "podcast_extended"]
    if present and any(not row["ok"] for row in present):
        size_ok = False
    report = {
        **_NO_LIVE,
        "episode_id": pack.episode_id,
        "tool": "distro",
        "display_name_lock": DISPLAY_NAME,
        "display_name_short": DISPLAY_NAME_SHORT,
        "pack_display_name": pack.display_name,
        "ok": not blockers,
        "blockers": codes(blockers),
        "gates": gate_matrix(blockers),
        "ordered_waves": list(ORDERED_WAVES),
        "separate_waves": list(SEPARATE_WAVES),
        "runners": _runner_view(pack, longform_url=longform_url, extended_go=extended_go),
        "thumbs": _thumb_report(pack),
        "picture_qc": {
            "passed": pack.picture_qc.get("passed") is True,
            "note_path": pack.picture_qc.get("note_path"),
        },
        "meta": {
            "title": pack.meta.get("title"),
            "inherits_locked_narration": pack.meta.get("inherits_locked_narration") is True,
            "claim_gated": pack.meta.get("claim_gated") is True,
            "sources_list": pack.meta.get("sources_list") or [],
        },
        "ingest": {
            "pc_pack_path": str(pc) if pc else pack.ingest.get("pc_pack_path"),
            "creators_session": pack.ingest.get("creators_session"),
            "box_studio_only": pack.ingest.get("box_studio_only") is True,
            "size_caps_ok": size_ok and not any(code == "gate_size_cap" for code in codes(blockers)),
            "checklist": rows,
        },
    }
    return report


def _emit_runner(
    pack: LoadedPack,
    out: Path,
    *,
    runner: str,
    blockers: list[Blocker],
    apply: bool,
    extra: dict | None = None,
) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        **_NO_LIVE,
        "runner": runner,
        "episode_id": pack.episode_id,
        "ok": not blockers,
        "dry_run": not apply,
        "applied": bool(apply and not blockers),
        "blockers": codes(blockers),
        "display_name_lock": DISPLAY_NAME,
        "note": "Local plan only. Live publish stays blocked.",
    }
    if extra:
        payload.update(extra)
    name = "status.json" if runner == "status" else f"{runner}.json"
    _write_json(out / "distro" / name, payload)
    outputs = [f"distro/{name}", f"{pack.episode_id}.machine.json"]
    if runner == "status":
        report = _base_report(pack, blockers, longform_url=None, extended_go=None)
        report["ok"] = not blockers
        report["blockers"] = codes(blockers)
        _write_json(out / "distro" / "status.json", report)
        (out / "distro" / "status.md").write_text(_status_md(report), encoding="utf-8")
        outputs = ["distro/status.json", "distro/status.md", f"{pack.episode_id}.machine.json"]
        payload = report
    if apply and not blockers:
        room = {
            **_NO_LIVE,
            "episode_id": pack.episode_id,
            "runner": runner,
            "urls": {"yt_long": None, "shorts": {}, "podcast": None, "podcast_extended": None},
            "local_plans": [f"distro/{name}"],
            "note": "Apply wrote a local plan. URLs stay empty. Live publish is blocked.",
        }
        _write_json(out / "distro" / "room-report.json", room)
        outputs.append("distro/room-report.json")
        payload["room_report"] = "distro/room-report.json"
    machine = _machine(pack, out, outputs, codes(blockers), tool=f"distro-{runner}")
    payload["machine"] = machine
    payload["outputs"] = outputs
    payload["out_dir"] = str(out)
    payload["distro_blocked"] = True
    payload["published"] = False
    payload["uploads"] = False
    return payload


def run_distro_status(
    pack_path: Path | str,
    *,
    out_dir: Path | str | None = None,
    allow_pwe: bool = False,
) -> dict:
    """Readiness report. Never publishes. Exit condition is the returned ``ok`` flag."""
    pack = load_pack(pack_path)
    out = Path(out_dir) if out_dir else Path("distro-runs") / pack.episode_id
    blockers = distro_blockers(pack, allow_pwe=allow_pwe)
    return _emit_runner(pack, out, runner="status", blockers=blockers, apply=False)


def run_distro_yt_long(
    pack_path: Path | str,
    *,
    apply: bool = False,
    out_dir: Path | str | None = None,
    allow_pwe: bool = False,
) -> dict:
    pack = load_pack(pack_path)
    out = Path(out_dir) if out_dir else Path("distro-runs") / pack.episode_id
    blockers = distro_blockers(pack, allow_pwe=allow_pwe)
    extra = {
        "wave": 1,
        "thumb": pack.stamps.get("thumb_yt_path"),
        "title": pack.meta.get("title"),
        "platform": "youtube",
        "platform_called": False,
    }
    return _emit_runner(pack, out, runner="yt-long", blockers=blockers, apply=apply, extra=extra)


def run_distro_shorts(
    pack_path: Path | str,
    *,
    longform_url: str | None = None,
    apply: bool = False,
    out_dir: Path | str | None = None,
    allow_pwe: bool = False,
) -> dict:
    pack = load_pack(pack_path)
    out = Path(out_dir) if out_dir else Path("distro-runs") / pack.episode_id
    blockers = shorts_blockers(pack, longform_url, allow_pwe=allow_pwe)
    hooks = pack.meta.get("shorts_hooks") if isinstance(pack.meta.get("shorts_hooks"), dict) else {}
    extra = {
        "wave": 2,
        "after": "yt-long",
        "longform_url": longform_url,
        "hooks": {letter: hooks.get(letter) for letter in ("A", "B", "C", "D")},
        "platform": "youtube-shorts",
        "platform_called": False,
    }
    return _emit_runner(pack, out, runner="shorts", blockers=blockers, apply=apply, extra=extra)


def run_distro_podcast(
    pack_path: Path | str,
    *,
    apply: bool = False,
    out_dir: Path | str | None = None,
    allow_pwe: bool = False,
) -> dict:
    pack = load_pack(pack_path)
    out = Path(out_dir) if out_dir else Path("distro-runs") / pack.episode_id
    blockers = podcast_blockers(pack, allow_pwe=allow_pwe)
    extended = pack.masters.get("podcast_extended") if isinstance(pack.masters.get("podcast_extended"), dict) else {}
    extra = {
        "wave": 3,
        "cover_locked": pack.cover.get("locked") is True,
        "audio": (pack.masters.get("podcast_yt_length") or {}).get("path")
        if isinstance(pack.masters.get("podcast_yt_length"), dict)
        else None,
        "includes_extended": False,
        "extended_path": None,
        "extended_separate_go": extended.get("separate_go", True),
        "platform": "podcast",
        "platform_called": False,
    }
    return _emit_runner(pack, out, runner="podcast", blockers=blockers, apply=apply, extra=extra)


def run_distro_podcast_extended(
    pack_path: Path | str,
    *,
    go_path: Path | str | None = None,
    apply: bool = False,
    out_dir: Path | str | None = None,
    allow_pwe: bool = False,
) -> dict:
    pack = load_pack(pack_path)
    out = Path(out_dir) if out_dir else Path("distro-runs") / pack.episode_id
    go = Path(go_path) if go_path else None
    blockers = podcast_extended_blockers(pack, go, allow_pwe=allow_pwe)
    node = pack.masters.get("podcast_extended") if isinstance(pack.masters.get("podcast_extended"), dict) else {}
    extra = {
        "wave": None,
        "separate_go": True,
        "in_yt_wave": False,
        "audio": node.get("path"),
        "platform": "podcast",
        "platform_called": False,
    }
    return _emit_runner(pack, out, runner="podcast-extended", blockers=blockers, apply=apply, extra=extra)
