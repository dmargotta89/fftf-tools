"""fftf edit-pass — first-pass episode master.

Dry-run is the default. ``--apply`` writes a local master and edit artifacts.
It does not launch Distro, spend, or publish. Spoken VO is read-only.
Lower-thirds come only from caption_safe or Verifier-approved quote cards.

Resolve is not bundled. ``--backend resolve`` blocks with ``resolve_unavailable``
unless ``--fallback-ffmpeg`` is set. There is no silent downgrade.

Specs stamped 2026-09-26: Episode Edit Module v1.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from fftf_tools.channel_profile import DISPLAY_NAME, LOUDNESS
from fftf_tools.episode_pack import Blocker, LoadedPack, hash_path, load_pack
from fftf_tools.gates import approved_cards, codes, edit_blockers, iter_size_rows
from fftf_tools.schema import (
    Asset,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    hold_tool_fences,
    write_machine,
)

REF_SAMPLE_N = 24
_FONT = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
_STAGES = (
    ("validate_pack", 10),
    ("select_refs", 25),
    ("estimate_grade", 40),
    ("build_timeline", 55),
    ("audio_mix", 70),
    ("render", 85),
    ("write_report", 100),
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def usable_frame_indices(n_frames: int) -> list[int]:
    """Interior frames only. Index 0 is never a video reference frame."""
    if n_frames <= 1:
        return []
    usable: list[int] = []
    last = n_frames - 1
    for index in range(n_frames):
        if index == 0 or index == last:
            continue
        center = (index + 0.5) / n_frames
        if center < 0.05 or center > 0.95:
            continue
        usable.append(index)
    return usable


def sample_indices(n_frames: int, n: int = REF_SAMPLE_N) -> list[int]:
    usable = usable_frame_indices(n_frames)
    if not usable:
        return []
    if len(usable) <= n:
        return usable
    last = len(usable) - 1
    picked: list[int] = []
    for step in range(n):
        pos = round(step * last / (n - 1)) if n > 1 else 0
        index = usable[pos]
        if index not in picked:
            picked.append(index)
    return picked


def _stats(image: Image.Image) -> dict:
    small = image.convert("RGB").resize((64, 36))
    raw = small.tobytes()
    count = len(raw) // 3
    reds = raw[0::3]
    greens = raw[1::3]
    blues = raw[2::3]
    red = sum(reds) / count
    green = sum(greens) / count
    blue = sum(blues) / count
    luma_px: list[float] = []
    sats: list[float] = []
    clipped = 0
    for index in range(count):
        pixel_r = reds[index]
        pixel_g = greens[index]
        pixel_b = blues[index]
        luma_px.append(0.2126 * pixel_r + 0.7152 * pixel_g + 0.0722 * pixel_b)
        peak = max(pixel_r, pixel_g, pixel_b)
        floor = min(pixel_r, pixel_g, pixel_b)
        sats.append(0.0 if peak == 0 else (peak - floor) / peak)
        if peak > 250 or floor < 5:
            clipped += 1
    width, height = 64, 36
    sharp_acc = 0.0
    sharp_n = 0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            center = luma_px[y * width + x]
            lap = (
                luma_px[y * width + x - 1]
                + luma_px[y * width + x + 1]
                + luma_px[(y - 1) * width + x]
                + luma_px[(y + 1) * width + x]
                - 4 * center
            )
            sharp_acc += lap * lap
            sharp_n += 1
    luma = sum(luma_px) / count
    cast = (abs(red - green) + abs(blue - green)) / 255.0
    return {
        "r": red,
        "g": green,
        "b": blue,
        "luma": luma,
        "cast": cast,
        "sat": sum(sats) / count,
        "clip": clipped / count,
        "sharp": sharp_acc / sharp_n if sharp_n else 0.0,
    }


def _fails_quality(stats: dict, motion: float) -> str | None:
    if stats["luma"] < 16:
        return "near_black"
    if stats["luma"] > 235:
        return "near_white"
    if stats["sat"] > 0.92 or stats["clip"] > 0.2:
        return "clip_or_saturation"
    if motion > 28:
        return "motion"
    return None


def _score(stats: dict, median_rgb: tuple[float, float, float]) -> dict:
    exposure = 1.0 - min(1.0, abs(stats["luma"] - 128.0) / 128.0)
    neutral = 1.0 - min(1.0, stats["cast"])
    sharp = min(1.0, stats["sharp"] / 400.0)
    dist = math.sqrt(
        (stats["r"] - median_rgb[0]) ** 2
        + (stats["g"] - median_rgb[1]) ** 2
        + (stats["b"] - median_rgb[2]) ** 2
    )
    represent = 1.0 - min(1.0, dist / 128.0)
    total = 0.30 * exposure + 0.25 * neutral + 0.20 * sharp + 0.25 * represent
    return {
        "exposure_mid": round(exposure, 4),
        "neutral": round(neutral, 4),
        "sharpness": round(sharp, 4),
        "representativeness": round(represent, 4),
        "total": round(total, 4),
    }


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def select_source_ref(frames: list[Path], *, sequence: bool) -> dict:
    """Pick a reference frame. A sequence never returns index 0."""
    if not frames:
        return _empty_ref("no_valid_ref_frame")
    if not sequence:
        image = Image.open(frames[0])
        stats = _stats(image)
        image.close()
        reason = _fails_quality(stats, 0.0)
        if reason:
            return _empty_ref("no_valid_ref_frame", kind="still", reject=reason)
        score = _score(stats, (stats["r"], stats["g"], stats["b"]))
        return {
            "frame_index": None,
            "kind": "still",
            "sampled_indices": [],
            "chosen_path": frames[0],
            "score": score["total"],
            "breakdown": score,
            "stats": stats,
            "blocker": None,
        }
    sampled = sample_indices(len(frames))
    if not sampled or 0 in sampled:
        return _empty_ref("no_valid_ref_frame", sampled=sampled)
    measured: list[tuple[int, dict, float]] = []
    for index in sampled:
        image = Image.open(frames[index])
        stats = _stats(image)
        image.close()
        motion = 0.0
        if index > 0:
            prev = Image.open(frames[index - 1])
            motion = _motion(stats, _stats(prev))
            prev.close()
        if _fails_quality(stats, motion):
            continue
        measured.append((index, stats, motion))
    if not measured:
        return _empty_ref("no_valid_ref_frame", sampled=sampled)
    median_rgb = (
        _median([item[1]["r"] for item in measured]),
        _median([item[1]["g"] for item in measured]),
        _median([item[1]["b"] for item in measured]),
    )
    ranked: list[tuple[float, int, dict, dict]] = []
    for index, stats, _motion_value in measured:
        if index == 0:
            continue
        score = _score(stats, median_rgb)
        ranked.append((score["total"], index, stats, score))
    if not ranked:
        return _empty_ref("no_valid_ref_frame", sampled=sampled)
    best = max(item[0] for item in ranked)
    tied = [item for item in ranked if item[0] == best]
    target = tied[len(tied) // 2][1]
    chosen = min(tied, key=lambda item: (abs(item[1] - target), item[1]))
    _total, index, stats, score = chosen
    return {
        "frame_index": index,
        "kind": "sequence",
        "sampled_indices": sampled,
        "chosen_path": frames[index],
        "score": score["total"],
        "breakdown": score,
        "stats": stats,
        "blocker": None,
    }


def _motion(left: dict, right: dict) -> float:
    return abs(left["luma"] - right["luma"])


def _empty_ref(blocker: str, *, kind: str = "sequence", sampled: list[int] | None = None, reject: str | None = None) -> dict:
    return {
        "frame_index": None,
        "kind": kind,
        "sampled_indices": sampled or [],
        "chosen_path": None,
        "score": None,
        "breakdown": {},
        "stats": None,
        "blocker": blocker,
        "reject": reject,
    }


def _sequence_frames(path: Path) -> list[Path]:
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg"})


def grade_params(src: dict, anchor: dict) -> dict:
    """Lightweight white-balance, exposure, and capped saturation toward the anchor."""
    src_g = max(src["g"], 1.0)
    anc_g = max(anchor["g"], 1.0)
    gain_r = ((anchor["r"] / anc_g) / (src["r"] / src_g)) if src["r"] > 1 else 1.0
    gain_b = ((anchor["b"] / anc_g) / (src["b"] / src_g)) if src["b"] > 1 else 1.0
    gain_r = _clamp(gain_r, 0.5, 1.5)
    gain_b = _clamp(gain_b, 0.5, 1.5)
    brightness = _clamp((anchor["luma"] - src["luma"]) / 255.0, -0.3, 0.3)
    sat_scale = _clamp(anchor["sat"] / src["sat"], 0.9, 1.1) if src["sat"] > 0 else 1.0
    exposure = 0.0
    if src["luma"] > 1 and anchor["luma"] > 1:
        exposure = _clamp(math.log2(anchor["luma"] / src["luma"]), -2.0, 2.0)
    return {
        "wb_gain_r": round(gain_r, 4),
        "wb_gain_g": 1.0,
        "wb_gain_b": round(gain_b, 4),
        "exposure_stops": round(exposure, 4),
        "brightness": round(brightness, 4),
        "contrast": 1.0,
        "saturation": round(sat_scale, 4),
        "gamma_r": round(_clamp(1.0 / gain_r, 0.7, 1.3), 4),
        "gamma_g": 1.0,
        "gamma_b": round(_clamp(1.0 / gain_b, 0.7, 1.3), 4),
    }


def _eq_filter(params: dict) -> str:
    return (
        "eq="
        f"brightness={params['brightness']}:"
        f"contrast={params['contrast']}:"
        f"saturation={params['saturation']}:"
        f"gamma_r={params['gamma_r']}:"
        f"gamma_g={params['gamma_g']}:"
        f"gamma_b={params['gamma_b']}"
    )


def _source_by_id(pack: LoadedPack) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for source in pack.sources:
        asset_id = str(source.get("asset_id") or "")
        if asset_id:
            found[asset_id] = source
    return found


def _choose_anchor(results: dict[str, dict], sources: dict[str, dict]) -> str | None:
    def ok(asset_id: str) -> bool:
        return results.get(asset_id, {}).get("blocker") is None and results.get(asset_id, {}).get("stats")

    primary = [
        asset_id
        for asset_id, source in sources.items()
        if source.get("role") == "primary" and source.get("type") == "camera" and ok(asset_id)
    ]
    if primary:
        return primary[0]
    cameras = [
        asset_id
        for asset_id, source in sources.items()
        if source.get("type") == "camera" and ok(asset_id)
    ]
    if cameras:
        return max(cameras, key=lambda asset_id: results[asset_id]["score"] or 0)
    heroes = [
        asset_id
        for asset_id, source in sources.items()
        if source.get("role") == "hero" and ok(asset_id)
    ]
    if heroes:
        return heroes[0]
    return None


def resolve_available() -> bool:
    """True only when a worker both opts in and can import Resolve's script module."""
    if os.environ.get("FFTF_RESOLVE_AVAILABLE") != "1":
        return False
    try:
        import DaVinciResolveScript  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def _write_json(path: Path, payload: dict) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _progress(
    path: Path,
    *,
    job_id: str,
    episode_id: str,
    backend: str,
    status: str,
    stage: str,
    pct: int,
    message: str,
    blockers: list[str],
    master: str | None,
    report: str | None,
    ref_dir: str | None,
    dry_run: bool,
    fallback_from: str | None,
) -> dict:
    payload = {
        "job_id": job_id,
        "episode_id": episode_id,
        "backend": backend,
        "status": status,
        "stage": stage,
        "pct": pct,
        "message": message,
        "blockers": blockers,
        "artifacts": {"master": master, "report": report, "ref_frames_dir": ref_dir},
        "updated_at": _now(),
        "distro_blocked": True,
        "published": False,
        "uploads": False,
        "dry_run": dry_run,
    }
    if fallback_from:
        payload["fallback_from"] = fallback_from
    _write_json(path, payload)
    return payload


def _public_ref(ref: dict) -> dict:
    path = ref.get("chosen_path")
    return {
        "frame_index": ref.get("frame_index"),
        "kind": ref.get("kind"),
        "sampled_indices": ref.get("sampled_indices") or [],
        "score": ref.get("score"),
        "breakdown": ref.get("breakdown") or {},
        "path": str(path) if path else None,
        "blocker": ref.get("blocker"),
    }


def _timeline(pack: LoadedPack, grades: dict[str, dict]) -> list[dict]:
    pacing = pack.edit.get("pacing") if isinstance(pack.edit.get("pacing"), dict) else {}
    min_cut = float(pacing.get("min_cut_s", 0.8))
    max_hold = float(pacing.get("max_still_hold_s", 5.0))
    segments: list[dict] = []
    for beat in pack.timeline:
        start = float(beat.get("t_start_s") or 0)
        end = float(beat.get("t_end_s") or start)
        window = max(0.0, end - start)
        broll = beat.get("broll") or []
        if not broll:
            broll = [{"asset_id": next(iter(grades), ""), "max_s": window or min_cut}]
        for item in broll:
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id") or "")
            hold = window or min_cut
            if item.get("max_s") is not None:
                hold = min(hold, float(item["max_s"]))
            hold = min(max(hold, min_cut), max_hold)
            segments.append(
                {
                    "beat_id": beat.get("beat_id"),
                    "asset_id": asset_id,
                    "duration_s": round(hold, 3),
                    "role": item.get("role"),
                    "grade": grades.get(asset_id, {}),
                }
            )
    return segments


def _audio_plan(pack: LoadedPack) -> dict:
    policy = pack.edit.get("audio") if isinstance(pack.edit.get("audio"), dict) else {}
    voice = float(policy.get("voice_lufs", LOUDNESS["voice_lufs"]))
    peak = float(policy.get("true_peak_dbtp", LOUDNESS["true_peak_dbtp"]))
    duck = float(policy.get("duck_music_db", LOUDNESS["duck_music_db"]))
    if pack.music_enabled:
        music = "duck_stub"
        reason = "Music is enabled. Duck depth is applied as a volume stub under the VO."
    else:
        music = "no-op"
        reason = "music.enabled is false. FFTF stays dry until music clearance. Duck path is a no-op."
    return {
        "voice_lufs": voice,
        "true_peak_dbtp": peak,
        "duck_music_db": duck,
        "music": music,
        "reason": reason,
        "filter": f"loudnorm=I={voice}:TP={peak}:LRA=11",
    }


def _ffprobe_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(cmd: list[str]) -> None:
    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ffmpeg failed").strip()
        raise RuntimeError(detail[-800:])


def _ff_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")


def _render_master(
    segments: list[dict],
    grades_full: dict[str, dict],
    vo_path: Path,
    out_path: Path,
    audio: dict,
    card_text: str | None,
    work: Path,
) -> None:
    work.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    textfile = None
    if card_text:
        textfile = work / "lower-third.txt"
        textfile.write_text(card_text, encoding="utf-8")
    for index, segment in enumerate(segments):
        asset_id = segment["asset_id"]
        ref = grades_full.get(asset_id) or {}
        image = ref.get("chosen_path")
        if image is None:
            raise RuntimeError(f"no graded still for {asset_id}")
        params = segment.get("grade") or grade_params(ref["stats"], ref["stats"])
        vf = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,"
            + _eq_filter(params)
        )
        if textfile is not None and index == 0 and _FONT.is_file():
            vf += (
                f",drawtext=fontfile='{_ff_path(_FONT)}':textfile='{_ff_path(textfile)}':"
                "fontsize=36:fontcolor=white:borderw=2:bordercolor=black:"
                "x=(w-text_w)/2:y=h-80"
            )
        part = work / f"part-{index:02d}.mp4"
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(image),
                "-t",
                f"{segment['duration_s']:.3f}",
                "-vf",
                vf,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(part),
            ]
        )
        parts.append(part)
    if len(parts) == 1:
        video = parts[0]
    else:
        concat = work / "concat.txt"
        concat.write_text("".join(f"file '{part.resolve()}'\n" for part in parts), encoding="utf-8")
        video = work / "video.mp4"
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                str(video),
            ]
        )
    total = sum(segment["duration_s"] for segment in segments)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-i",
            str(vo_path),
            "-filter_complex",
            f"[1:a]{audio['filter']},apad[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-t",
            f"{total:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(out_path),
        ]
    )


def _report(
    pack: LoadedPack,
    *,
    backend: str,
    dry_run: bool,
    fallback_from: str | None,
    blockers: list[Blocker],
    refs: dict[str, dict],
    anchor: str | None,
    grades: dict[str, dict],
    segments: list[dict],
    audio: dict,
    cards: list[dict],
    master: Path | None,
) -> str:
    lines = [
        f"# Edit report — {pack.episode_id}",
        "",
        channel_line(),
        "Distro: blocked (`distro_blocked` is true). This module does not publish or call YouTube or Spotify.",
        "Spoken VO was not rewritten. Lower-thirds use caption_safe or Verifier-approved quote cards only.",
        "",
        f"- Backend: {backend}",
        f"- Dry-run: {str(dry_run).lower()}",
        f"- Display name lock: {DISPLAY_NAME}",
    ]
    if fallback_from:
        lines.append(f"- Fallback: {backend} requested via flag after {fallback_from} was unavailable.")
    lines.extend(["", "## Gates", ""])
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker.code}`: {blocker.detail}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Reference frames", ""])
    lines.append("Video sequences skip index 0 and the first/last 5 percent. Frame 0 is never the auto ref.")
    if anchor:
        lines.append(f"- Global anchor: `{anchor}`")
    for asset_id, ref in refs.items():
        lines.append(
            f"- `{asset_id}` kind={ref.get('kind')} frame_index={ref.get('frame_index')} "
            f"score={ref.get('score')} sampled={ref.get('sampled_indices')}"
        )
    lines.extend(["", "## Grade", ""])
    for asset_id, params in grades.items():
        lines.append(f"- `{asset_id}`: {params}")
    lines.extend(["", "## Timeline", ""])
    for segment in segments:
        lines.append(
            f"- {segment.get('beat_id')} · {segment.get('asset_id')} · {segment.get('duration_s')}s"
        )
    lines.extend(
        [
            "",
            "## Audio",
            "",
            f"- Loudness target: {audio.get('voice_lufs')} LUFS, true peak {audio.get('true_peak_dbtp')} dBTP.",
            f"- Music: {audio.get('music')}. {audio.get('reason')}",
            "",
            "## Lower thirds",
            "",
        ]
    )
    if cards:
        for card in cards:
            lines.append(f"- ({card['source']}) {card['text']}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Distro handoff",
            "",
            "Assembly fields are in `edit/assembly-pack.json`. Picture QC is not cleared by this module.",
            f"- Master: {master if master else '(not written)'}",
            "",
        ]
    )
    return "\n".join(lines)


def _assembly(
    pack: LoadedPack,
    *,
    master: Path | None,
    out: Path,
) -> dict:
    master_sha = hash_path(master) if master is not None and master.is_file() else None
    rel_master = None
    if master is not None and master.is_file():
        try:
            rel_master = str(master.relative_to(out))
        except ValueError:
            rel_master = str(master)
    return {
        "episode_id": pack.episode_id,
        "channel": pack.channel_slug,
        "display_name_lock": DISPLAY_NAME,
        "display_name_short": pack.display_short,
        "distro_blocked": True,
        "published": False,
        "verdict": {
            "path": str(pack.verdict_path) if pack.verdict_path else None,
            "status": pack.verdict.get("status"),
            "spoken_word_count": pack.verdict.get("spoken_word_count"),
            "wording_hash": pack.verdict.get("wording_hash"),
            "match_vs_narration": pack.verdict.get("match_vs_narration"),
            "review_path": str(pack.review_path) if pack.review_path else None,
        },
        "stamps": pack.stamps,
        "masters": {
            "longform": {"path": rel_master, "sha256": master_sha},
            "shorts": [{"id": letter, "path": None, "sha256": None} for letter in ("A", "B", "C", "D")],
            "podcast_yt_length": {"path": None, "sha256": None},
            "podcast_extended": {"path": None, "sha256": None, "separate_go": True},
        },
        "picture_qc": {
            "passed": False,
            "note_path": None,
            "detail": "Edit does not clear picture QC. Distro stays blocked until Cut records a QC note.",
        },
        "meta": pack.meta,
        "asset_index_ref": pack.manifest.get("asset_index_ref"),
        "caption_safe_ref": pack.manifest.get("caption_safe_ref"),
        "ingest": pack.ingest,
        "size_checklist": iter_size_rows(pack),
    }


def _machine(pack: LoadedPack, out: Path, outputs: list[str], tool_blockers: list[str]) -> dict:
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
                    path=asset.rel or (str(asset.path) if asset.path else ""),
                    role=asset.role or asset.asset_id or "asset",
                    license=asset.license,
                    sha256=asset.sha256,
                )
            )
        else:
            assets.append(Asset(path=asset.rel or "", role=asset.role or "asset"))
    for name in outputs:
        assets.append(Asset(path=name, role="edit-output"))
    payload = contract_payload(
        pack.episode_id,
        sources=sources,
        fences=fences,
        asset_index=assets,
        tool="edit-pass",
        channel=DISPLAY_NAME,
        channel_short=pack.display_short or "FFTF",
        uploads=False,
        published=False,
        blockers=tool_blockers,
        outputs=outputs,
    )
    return write_machine(out / f"{pack.episode_id}.machine.json", payload)


def find_progress(job: str) -> Path | None:
    candidate = Path(job)
    if candidate.is_file() and candidate.name == "progress.json":
        return candidate
    if candidate.is_dir():
        nested = candidate / "edit" / "progress.json"
        if nested.is_file():
            return nested
    for base in (Path("edit-jobs"), Path.cwd() / "edit-jobs"):
        nested = base / job / "edit" / "progress.json"
        if nested.is_file():
            return nested
    return None


def run_edit_status(job: str) -> dict:
    path = find_progress(job)
    if path is None:
        return {
            "ok": False,
            "status": "failed",
            "blockers": ["job_not_found"],
            "message": f"No progress.json for {job}",
            "distro_blocked": True,
            "published": False,
            "outputs": [],
        }
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["ok"] = payload.get("status") == "succeeded"
    payload["distro_blocked"] = True
    payload["outputs"] = [str(path)]
    return payload


def run_edit_pass(
    pack_path: Path | str,
    *,
    backend: str | None = None,
    apply: bool = False,
    fallback_ffmpeg: bool = False,
    allow_pwe: bool = False,
    out_dir: Path | str | None = None,
) -> dict:
    """Validate a pack and, on ``--apply``, write a first-pass master.

    Dry-run plans reference frames and grades and does not write a master.
    """
    pack = load_pack(pack_path)
    requested = backend or str(pack.edit.get("backend") or "ffmpeg")
    if requested not in {"ffmpeg", "resolve"}:
        requested = "ffmpeg"
    job_id = f"{pack.episode_id}-{uuid.uuid4().hex[:8]}"
    out = Path(out_dir) if out_dir else Path("edit-jobs") / job_id
    edit_dir = out / "edit"
    edit_dir.mkdir(parents=True, exist_ok=True)
    progress_path = edit_dir / "progress.json"
    report_path = edit_dir / "report.md"
    dry_run = not apply
    active_backend = requested
    fallback_from = None
    blocker_list: list[Blocker] = []
    refs: dict[str, dict] = {}
    grades: dict[str, dict] = {}
    segments: list[dict] = []
    audio = _audio_plan(pack)
    cards = approved_cards(pack.caption)
    master: Path | None = None
    vo_before = None
    if pack.vo_path is not None and pack.vo_path.is_file():
        vo_before = hash_path(pack.vo_path)
    narration_before = None
    if pack.narration_path is not None and pack.narration_path.is_file():
        narration_before = hash_path(pack.narration_path)
    caption_path = pack.path(pack.manifest.get("caption_safe_ref"))
    caption_before = hash_path(caption_path) if caption_path is not None and caption_path.is_file() else None

    def snapshot(status: str, stage: str, pct: int, message: str) -> None:
        _progress(
            progress_path,
            job_id=job_id,
            episode_id=pack.episode_id,
            backend=active_backend,
            status=status,
            stage=stage,
            pct=pct,
            message=message,
            blockers=codes(blocker_list),
            master=str(master) if master else None,
            report=str(report_path) if report_path.is_file() else None,
            ref_dir=str(edit_dir / "ref-frames") if (edit_dir / "ref-frames").is_dir() else None,
            dry_run=dry_run,
            fallback_from=fallback_from,
        )

    snapshot("running", "validate_pack", 10, "Validating pack gates.")
    blocker_list = edit_blockers(pack, allow_pwe=allow_pwe)
    if blocker_list:
        _finish_blocked(
            pack,
            out,
            report_path,
            progress_path,
            job_id,
            active_backend,
            dry_run,
            fallback_from,
            blocker_list,
            refs,
            None,
            grades,
            segments,
            audio,
            cards,
            "validate_pack",
            10,
            "Bake refused.",
        )
        return _result(
            pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, None, False
        )

    snapshot("running", "select_refs", 25, "Selecting reference frames.")
    sources = _source_by_id(pack)
    for asset_id, source in sources.items():
        path = pack.path(source.get("path"))
        if path is None or not path.exists():
            refs[asset_id] = _empty_ref("no_valid_ref_frame")
            continue
        if path.is_dir():
            frames = _sequence_frames(path)
            refs[asset_id] = select_source_ref(frames, sequence=True)
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            refs[asset_id] = select_source_ref([path], sequence=False)
        else:
            refs[asset_id] = _empty_ref("no_valid_ref_frame", kind="unsupported")
    anchor = _choose_anchor(refs, sources)
    if anchor is None:
        blocker_list = [Blocker("no_valid_ref_frame", "No source produced a valid reference frame.")]
        _finish_blocked(
            pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
            blocker_list, refs, anchor, grades, segments, audio, cards, "select_refs", 25,
            "Bake refused. No valid reference frame.",
        )
        return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)

    snapshot("running", "estimate_grade", 40, "Estimating grade toward the anchor.")
    anchor_stats = refs[anchor]["stats"]
    for asset_id, ref in refs.items():
        if ref.get("stats"):
            grades[asset_id] = grade_params(ref["stats"], anchor_stats)
    grade_doc = {
        "episode_id": pack.episode_id,
        "backend": active_backend,
        "distro_blocked": True,
        "anchor": {"asset_id": anchor, **_public_ref(refs[anchor])},
        "clips": [
            {"asset_id": asset_id, "params": params, **_public_ref(refs[asset_id])}
            for asset_id, params in grades.items()
        ],
        "audio": audio,
    }
    _write_json(edit_dir / "grade.json", grade_doc)

    snapshot("running", "build_timeline", 55, "Building the timeline from the manifest.")
    segments = _timeline(pack, grades)
    if not segments:
        blocker_list = [Blocker("gate_pack_invalid", "Timeline has no beats to cut.")]
        _finish_blocked(
            pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
            blocker_list, refs, anchor, grades, segments, audio, cards, "build_timeline", 55,
            "Bake refused. Timeline is empty.",
        )
        return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)

    snapshot("running", "audio_mix", 70, "Planning loudness. Music duck is a stub when enabled.")

    if requested == "resolve" and not resolve_available():
        if not fallback_ffmpeg:
            blocker_list = [
                Blocker(
                    "resolve_unavailable",
                    "DaVinci Resolve is not on this worker. Refusing to downgrade. Pass --fallback-ffmpeg to use FFmpeg.",
                )
            ]
            active_backend = "resolve"
            _finish_blocked(
                pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
                blocker_list, refs, anchor, grades, segments, audio, cards, "render", 85,
                "Resolve unavailable. FFmpeg was not substituted.",
            )
            return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)
        fallback_from = "resolve"
        active_backend = "ffmpeg"

    snapshot("running", "render", 85, "Dry-run skipped the master." if dry_run else "Rendering the FFmpeg master.")
    if not dry_run:
        if active_backend != "ffmpeg":
            blocker_list = [Blocker("resolve_unavailable", "Resolve deliver is not configured on this worker.")]
            _finish_blocked(
                pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
                blocker_list, refs, anchor, grades, segments, audio, cards, "render", 85,
                "Resolve deliver is not configured.",
            )
            return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)
        if not _ffprobe_ok():
            blocker_list = [Blocker("ffmpeg_unavailable", "ffmpeg is not on PATH.")]
            _finish_blocked(
                pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
                blocker_list, refs, anchor, grades, segments, audio, cards, "render", 85,
                "ffmpeg is not on PATH.",
            )
            return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)
        version = 1
        master = out / "masters" / f"{episode_prefix_file(pack.episode_id)}-edit-v{version}.mp4"
        card_line = cards[0]["text"] if cards else None
        try:
            try:
                _render_master(segments, refs, pack.vo_path, master, audio, card_line, edit_dir / "render")
            except RuntimeError:
                if not card_line:
                    raise
                _render_master(segments, refs, pack.vo_path, master, audio, None, edit_dir / "render")
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            blocker_list = [Blocker("ffmpeg_render_failed", str(exc)[:500])]
            master = None
            _finish_blocked(
                pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
                blocker_list, refs, anchor, grades, segments, audio, cards, "render", 85,
                "FFmpeg render failed.",
            )
            return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)
        ref_dir = edit_dir / "ref-frames"
        ref_dir.mkdir(parents=True, exist_ok=True)
        for asset_id, ref in refs.items():
            chosen = ref.get("chosen_path")
            if chosen is not None and Path(chosen).is_file():
                target = ref_dir / f"{asset_id}.png"
                with Image.open(chosen) as image:
                    image.save(target)

    if vo_before is not None and hash_path(pack.vo_path) != vo_before:
        blocker_list = [Blocker("gate_vo_rewritten", "VO bytes changed during edit-pass.")]
    if narration_before is not None and hash_path(pack.narration_path) != narration_before:
        blocker_list = [Blocker("gate_vo_rewritten", "Narration bytes changed during edit-pass.")]
    if caption_before is not None and caption_path is not None and hash_path(caption_path) != caption_before:
        blocker_list = [Blocker("gate_vo_rewritten", "caption_safe bytes changed during edit-pass.")]
    if blocker_list:
        _finish_blocked(
            pack, out, report_path, progress_path, job_id, active_backend, dry_run, fallback_from,
            blocker_list, refs, anchor, grades, segments, audio, cards, "render", 85,
            "Bake refused. Spoken files changed.",
        )
        return _result(pack, job_id, out, active_backend, dry_run, fallback_from, blocker_list, refs, anchor, False)

    _write_json(
        edit_dir / "lower-thirds.json",
        {
            "episode_id": pack.episode_id,
            "distro_blocked": True,
            "notes_used": False,
            "cards": cards,
        },
    )
    report_path.write_text(
        _report(
            pack,
            backend=active_backend,
            dry_run=dry_run,
            fallback_from=fallback_from,
            blockers=[],
            refs=refs,
            anchor=anchor,
            grades=grades,
            segments=segments,
            audio=audio,
            cards=cards,
            master=master,
        ),
        encoding="utf-8",
    )
    _write_json(edit_dir / "assembly-pack.json", _assembly(pack, master=master, out=out))
    outputs = [
        "edit/progress.json",
        "edit/report.md",
        "edit/grade.json",
        "edit/lower-thirds.json",
        "edit/assembly-pack.json",
        f"{pack.episode_id}.machine.json",
    ]
    if master is not None:
        outputs.append(str(master.relative_to(out)))
    machine = _machine(pack, out, outputs, [])
    message = "Dry-run planned the first pass. No master written." if dry_run else "First-pass master written. Distro remains blocked."
    progress = _progress(
        progress_path,
        job_id=job_id,
        episode_id=pack.episode_id,
        backend=active_backend,
        status="succeeded",
        stage="write_report",
        pct=100,
        message=message,
        blockers=[],
        master=str(master) if master else None,
        report=str(report_path),
        ref_dir=str(edit_dir / "ref-frames") if master is not None else None,
        dry_run=dry_run,
        fallback_from=fallback_from,
    )
    anchor_ref = refs.get(anchor) or {}
    return {
        "ok": True,
        "status": "succeeded",
        "dry_run": dry_run,
        "applied": apply,
        "backend": active_backend,
        "fallback_from": fallback_from,
        "episode_id": pack.episode_id,
        "job_id": job_id,
        "blockers": [],
        "ref_frame_index": anchor_ref.get("frame_index"),
        "sampled_indices": anchor_ref.get("sampled_indices") or [],
        "anchor": anchor,
        "outputs": outputs,
        "out_dir": str(out),
        "progress_path": str(progress_path),
        "distro_blocked": True,
        "published": False,
        "uploads": False,
        "machine": machine,
        "progress": progress,
    }


def episode_prefix_file(episode_id: str) -> str:
    from fftf_tools.episode_pack import episode_prefix

    return episode_prefix(episode_id)


def _finish_blocked(
    pack: LoadedPack,
    out: Path,
    report_path: Path,
    progress_path: Path,
    job_id: str,
    backend: str,
    dry_run: bool,
    fallback_from: str | None,
    blockers: list[Blocker],
    refs: dict,
    anchor: str | None,
    grades: dict,
    segments: list,
    audio: dict,
    cards: list,
    stage: str,
    pct: int,
    message: str,
) -> None:
    report_path.write_text(
        _report(
            pack,
            backend=backend,
            dry_run=dry_run,
            fallback_from=fallback_from,
            blockers=blockers,
            refs=refs,
            anchor=anchor,
            grades=grades,
            segments=segments,
            audio=audio,
            cards=cards,
            master=None,
        ),
        encoding="utf-8",
    )
    _machine(pack, out, ["edit/progress.json", "edit/report.md", f"{pack.episode_id}.machine.json"], codes(blockers))
    _progress(
        progress_path,
        job_id=job_id,
        episode_id=pack.episode_id,
        backend=backend,
        status="blocked",
        stage=stage,
        pct=pct,
        message=message,
        blockers=codes(blockers),
        master=None,
        report=str(report_path),
        ref_dir=None,
        dry_run=dry_run,
        fallback_from=fallback_from,
    )


def _result(
    pack: LoadedPack,
    job_id: str,
    out: Path,
    backend: str,
    dry_run: bool,
    fallback_from: str | None,
    blockers: list[Blocker],
    refs: dict,
    anchor: str | None,
    ok: bool,
) -> dict:
    anchor_ref = refs.get(anchor) or {} if anchor else {}
    return {
        "ok": ok,
        "status": "succeeded" if ok else "blocked",
        "dry_run": dry_run,
        "applied": not dry_run and ok,
        "backend": backend,
        "fallback_from": fallback_from,
        "episode_id": pack.episode_id,
        "job_id": job_id,
        "blockers": codes(blockers),
        "ref_frame_index": anchor_ref.get("frame_index"),
        "sampled_indices": anchor_ref.get("sampled_indices") or [],
        "anchor": anchor,
        "outputs": ["edit/progress.json", "edit/report.md", f"{pack.episode_id}.machine.json"],
        "out_dir": str(out),
        "progress_path": str(out / "edit" / "progress.json"),
        "distro_blocked": True,
        "published": False,
        "uploads": False,
    }
