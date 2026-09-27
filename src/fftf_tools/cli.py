"""fftf CLI — From Fiction to Fact production helpers.

Pipeline commands write a machine contract with distro_blocked true.
They do not unlock Distro, publish, call YouTube or Spotify, or spend money.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from fftf_tools.brief_pack import run_brief_pack
from fftf_tools.claim_gate import run_claim_gate
from fftf_tools.distro_pack import run_distro_pack
from fftf_tools.distro_runners import (
    run_distro_podcast,
    run_distro_podcast_extended,
    run_distro_shorts,
    run_distro_status,
    run_distro_yt_long,
)
from fftf_tools.drive_checklist import write_drive_checklist
from fftf_tools.duck_sheet import run_duck_sheet
from fftf_tools.edit_pass import run_edit_pass, run_edit_status
from fftf_tools.picture_sync import run_picture_sync
from fftf_tools.schema import ContractError
from fftf_tools.script_strip import run_script_strip
from fftf_tools.shorts_cutter import run_shorts_cutter
from fftf_tools.thumb_pack import run_thumb_pack
from fftf_tools.thumb_safe import draw_thumb_safe
from fftf_tools.vo_check import run_vo_check


def _guard(fn):
    try:
        return fn()
    except ContractError as exc:
        raise click.ClickException(str(exc)) from exc


def _emit(payload: dict, lines: list[str], as_json: bool) -> None:
    lines = [*lines, "distro_blocked: true"]
    if as_json:
        for line in lines:
            click.echo(line, err=True)
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    for line in lines:
        click.echo(line)


def _wrote(payload: dict) -> list[str]:
    return [f"wrote {name}" for name in payload.get("outputs", [])]


@click.group()
@click.version_option(package_name="fftf-tools")
def main() -> None:
    """From Fiction to Fact (FFTF) production helpers.

    Pipeline commands keep distro_blocked true. They never publish.
    """


@main.command("vo-check")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--min-min", default=8.0, show_default=True, type=float, help="Min duration minutes (YT).")
@click.option("--max-min", default=12.0, show_default=True, type=float, help="Max duration minutes (YT).")
def vo_check_cmd(path: Path, min_min: float, max_min: float) -> None:
    """Validate VO-timing markdown (exit 0 PASS / 1 FAIL).

    \b
    Examples:
      fftf vo-check samples/ep03-watergate-v1.1-vo-timing-v3.md
      fftf vo-check path/to/vo-timing.md --min-min 8 --max-min 12
    """
    code = run_vo_check(path, min_min=min_min, max_min=max_min)
    sys.exit(code)


@main.command("duck-sheet")
@click.argument("clip_notes", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--vo", "vo_timing", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Optional VO-timing file.")
@click.option("-o", "out_prefix", default="duck-cues", show_default=True, help="Output prefix for .csv and .md.")
def duck_sheet_cmd(clip_notes: Path, vo_timing: Path | None, out_prefix: str) -> None:
    """Parse CLIP-NOTES / duck-cues markdown; emit CSV + MD cue sheets.

    \b
    Examples:
      fftf duck-sheet samples/CLIP-NOTES.md -o /tmp/ep03-duck
      fftf duck-sheet samples/CUT-AV-DUCK-CUES-2026-09-24.md --vo samples/ep03-watergate-v1.1-vo-timing-v3.md -o /tmp/ep03-cues
    """
    run_duck_sheet(clip_notes, vo_timing=vo_timing, out_prefix=out_prefix)


@main.command("drive-checklist")
@click.option("--ep", required=True, type=int, help="Episode number.")
@click.option("--title", required=True, type=str, help="Episode title.")
@click.option("-o", "out_file", default=None, type=click.Path(path_type=Path), help="Output markdown file.")
def drive_checklist_cmd(ep: int, title: str, out_file: Path | None) -> None:
    """Write a Drive episode checklist markdown.

    \b
    Examples:
      fftf drive-checklist --ep 3 --title "Watergate" -o /tmp/ep03-drive-checklist.md
    """
    write_drive_checklist(ep=ep, title=title, out_file=out_file)


@main.command("thumb-safe")
@click.argument("zone_image", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "overlay", default=None, type=click.Path(path_type=Path), help="Overlay PNG path.")
@click.option("--side", default=0.10, show_default=True, type=float)
@click.option("--top", default=0.12, show_default=True, type=float)
@click.option("--bottom", default=0.12, show_default=True, type=float)
def thumb_safe_cmd(
    zone_image: Path,
    overlay: Path | None,
    side: float,
    top: float,
    bottom: float,
) -> None:
    """Draw thumbnail safe-zone overlay; warn if not 1280x720.

    \b
    Examples:
      fftf thumb-safe /path/to/thumb.png -o /tmp/thumb-safe.png --side 0.10 --top 0.12 --bottom 0.12
    """
    draw_thumb_safe(
        zone_image,
        overlay=overlay,
        side=side,
        top=top,
        bottom=bottom,
    )


@main.command("distro-pack")
@click.option("--ep", required=True, type=click.IntRange(min=1), help="Episode number.")
@click.option("--title", required=True, type=str, help="Episode title.")
@click.option(
    "--draft",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Stamped draft or narration-only markdown.",
)
@click.option(
    "--vo",
    "vo_timing",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional VO-timing markdown for chapters.",
)
@click.option(
    "--thumb",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional thumbnail path. Recorded only; not uploaded.",
)
@click.option(
    "-o",
    "out_dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Output directory (default distro/epXX).",
)
def distro_pack_cmd(
    ep: int,
    title: str,
    draft: Path,
    vo_timing: Path | None,
    thumb: Path | None,
    out_dir: Path | None,
) -> None:
    """Write a local Studio paste pack. Does not upload or unlock Distro.

    \b
    Examples:
      fftf distro-pack --ep 3 --title "Watergate" \\
        --draft samples/ep03-watergate-v1.1-vo-timing-v3.md \\
        --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \\
        --thumb path/to/thumb.png -o /tmp/distro-ep03
    """
    _guard(
        lambda: run_distro_pack(
            ep=ep,
            title=title,
            draft=draft,
            vo_timing=vo_timing,
            thumb=thumb,
            out_dir=out_dir,
        )
    )


@main.command("shorts-cutter")
@click.option("--ep", required=True, type=click.IntRange(min=1), help="Episode number.")
@click.option(
    "--vo",
    "vo_timing",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="VO-timing markdown.",
)
@click.option(
    "--clips",
    "clip_notes",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional CLIP-NOTES markdown.",
)
@click.option("--title", default=None, type=str, help="Optional episode title.")
@click.option(
    "-o",
    "out_dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Output directory (default shorts/epXX).",
)
def shorts_cutter_cmd(
    ep: int,
    vo_timing: Path,
    clip_notes: Path | None,
    title: str | None,
    out_dir: Path | None,
) -> None:
    """Write a 4-cut Shorts bake brief. Does not render video.

    \b
    Examples:
      fftf shorts-cutter --ep 3 --title "Watergate" \\
        --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \\
        --clips samples/CLIP-NOTES.md -o /tmp/shorts-ep03
    """
    _guard(
        lambda: run_shorts_cutter(
            ep=ep,
            vo_timing=vo_timing,
            clip_notes=clip_notes,
            title=title,
            out_dir=out_dir,
        )
    )


@main.command("brief-pack")
@click.option("--topic", required=True, help="Episode topic. Research is not invented here.")
@click.option("--year-window", required=True, help="Year or range the agent will research, for example 1974.")
@click.option("--fences", default=None, help="JSON list, or a path to one. Optional.")
@click.option("--episode-id", default=None, help="Slug such as ep04-glomar-azorian. Defaults to ep-<topic>.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the machine JSON block on stdout.")
def brief_pack_cmd(topic: str, year_window: str, fences: str | None, episode_id: str | None, out_dir: Path | None, as_json: bool) -> None:
    """Write a brief skeleton, ASSET-HUNT.md, and a machine JSON block.

    Source URLs are PLACEHOLDER. Distro stays blocked.

    \b
    Examples:
      fftf brief-pack --topic "Glomar and Project Azorian" --year-window "1974" \\
        --episode-id ep04-glomar-azorian -o /tmp/ep04
    """
    payload = _guard(
        lambda: run_brief_pack(
            topic=topic,
            year_window=year_window,
            fences=fences,
            out_dir=out_dir,
            episode_id=episode_id,
        )
    )
    _emit(payload, _wrote(payload), as_json)


@main.command("claim-gate")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--sources", default=None, help="JSON list of {n, url, label}, or a path. Optional.")
@click.option("--fences", default=None, help="JSON list of fences, or a path. Optional.")
@click.option("--narration", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="narration-only file to match against the draft.")
@click.option("--episode-id", default=None, help="Override episode id.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the machine JSON block on stdout.")
def claim_gate_cmd(path: Path, sources: str | None, fences: str | None, narration: Path | None, episode_id: str | None, out_dir: Path | None, as_json: bool) -> None:
    """Write a verifier report. Exit 1 on FAIL. Distro stays blocked.

    \b
    Examples:
      fftf claim-gate /tmp/ep04/ep04-glomar-azorian-brief.md -o /tmp/ep04/claim-1
      fftf claim-gate /tmp/ep04/script/draft.md --narration /tmp/ep04/script/narration-only.md -o /tmp/ep04/claim-2
    """
    payload = _guard(
        lambda: run_claim_gate(
            path,
            sources=sources,
            fences=fences,
            narration=narration,
            out_dir=out_dir,
            episode_id=episode_id,
        )
    )
    _emit(payload, [f"verdict: {payload['verdict']}", *_wrote(payload)], as_json)
    if payload["verdict"] == "FAIL":
        sys.exit(1)


@main.command("script-strip")
@click.argument("brief", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--locks", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Locks JSON: vocab, naming, fences, cold_open_rules, envelope.")
@click.option("--episode-id", default=None, help="Override episode id.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the machine JSON block on stdout.")
def script_strip_cmd(brief: Path, locks: Path, episode_id: str | None, out_dir: Path | None, as_json: bool) -> None:
    """Write draft, narration-only, VO-timing, and delta templates.

    v1 uses TODO markers instead of a full documentary. Word counts are real.
    Spoken files omit the locked vocab. Distro stays blocked.

    \b
    Examples:
      fftf script-strip /tmp/ep04/ep04-glomar-azorian-brief.md --locks /tmp/locks.json -o /tmp/ep04/script
    """
    payload = _guard(
        lambda: run_script_strip(
            brief,
            locks,
            out_dir=out_dir,
            episode_id=episode_id,
        )
    )
    _emit(
        payload,
        [f"spoken_word_count: {payload.get('spoken_word_count')}", *_wrote(payload)],
        as_json,
    )


@main.command("picture-sync")
@click.argument("vo_timing", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("clip_notes", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--assets", "assets_path", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Optional asset-index JSON.")
@click.option("--episode-id", default=None, help="Override episode id.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the machine JSON block on stdout.")
def picture_sync_cmd(vo_timing: Path, clip_notes: Path, assets_path: Path | None, episode_id: str | None, out_dir: Path | None, as_json: bool) -> None:
    """Write SHOT-MAP, DUCK-SCHEDULE, and a picture-sync check.

    Reuses duck-sheet parsing. Distro stays blocked.

    \b
    Examples:
      fftf picture-sync /tmp/ep04/script/vo-timing.md samples/CLIP-NOTES.md -o /tmp/ep04/picture
    """
    payload = _guard(
        lambda: run_picture_sync(
            vo_timing,
            clip_notes,
            assets_path=assets_path,
            out_dir=out_dir,
            episode_id=episode_id,
        )
    )
    _emit(payload, [f"ducks: {len(payload.get('ducks', []))}", *_wrote(payload)], as_json)


@main.command("thumb-pack")
@click.option("--title-a", required=True, help="Title candidate A.")
@click.option("--title-b", required=True, help="Title candidate B.")
@click.option("--title-c", required=True, help="Title candidate C.")
@click.option("--still", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Optional still. Contained and padded. No generative API.")
@click.option("--episode-id", default=None, help="Override episode id. Default ep-thumb.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the machine JSON block on stdout.")
def thumb_pack_cmd(title_a: str, title_b: str, title_c: str, still: Path | None, episode_id: str | None, out_dir: Path | None, as_json: bool) -> None:
    """Write A/B/C thumb PNGs, thumb-brief.md, and a machine block.

    Without a still, Pillow draws title cards on a dark field. Distro stays blocked.

    \b
    Examples:
      fftf thumb-pack --episode-id ep04-glomar-azorian \\
        --title-a "The ship" --title-b "The cover" --title-c "The files" -o /tmp/ep04/thumb
    """
    payload = _guard(
        lambda: run_thumb_pack(
            title_a,
            title_b,
            title_c,
            still=still,
            out_dir=out_dir,
            episode_id=episode_id,
        )
    )
    _emit(payload, [f"safe_zone_ok: {payload.get('safe_zone_ok')}", *_wrote(payload)], as_json)


def _finish(payload: dict, lines: list[str], as_json: bool) -> None:
    _emit(payload, lines, as_json)
    if not payload.get("ok", True):
        sys.exit(1)


@main.group("edit-pass", invoke_without_command=True)
@click.pass_context
@click.option("--pack", default=None, type=click.Path(path_type=Path), help="Assembled episode pack directory.")
@click.option("--backend", default=None, type=click.Choice(["ffmpeg", "resolve"]), help="Override manifest edit.backend.")
@click.option("--dry-run/--apply", default=True, help="Dry-run is the default. --apply writes a local master and does not publish.")
@click.option("--fallback-ffmpeg", is_flag=True, help="If Resolve is missing, use FFmpeg. Without this flag Resolve is not downgraded.")
@click.option("--allow-pwe", is_flag=True, help="Allow a PWE verdict when CoS has explicitly allowed it.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path), help="Output directory.")
@click.option("--json", "as_json", is_flag=True, help="Print the result JSON on stdout.")
def edit_pass_group(ctx: click.Context, pack: Path | None, backend: str | None, dry_run: bool, fallback_ffmpeg: bool, allow_pwe: bool, out_dir: Path | None, as_json: bool) -> None:
    """First-pass edit. Dry-run default. Does not publish or rewrite spoken VO.

    \b
    Examples:
      fftf edit-pass --pack /tmp/ep05-pack -o /tmp/ep05-edit
      fftf edit-pass --pack /tmp/ep05-pack --apply -o /tmp/ep05-edit
      fftf edit-pass status --job /tmp/ep05-edit
    """
    if ctx.invoked_subcommand is not None:
        return
    if pack is None:
        raise click.UsageError("Missing option '--pack'.")
    payload = _guard(
        lambda: run_edit_pass(
            pack,
            backend=backend,
            apply=not dry_run,
            fallback_ffmpeg=fallback_ffmpeg,
            allow_pwe=allow_pwe,
            out_dir=out_dir,
        )
    )
    lines = [
        f"status: {payload.get('status')}",
        f"backend: {payload.get('backend')}",
        f"dry-run: {str(payload.get('dry_run')).lower()}",
    ]
    if payload.get("ref_frame_index") is not None:
        lines.append(f"ref_frame_index: {payload.get('ref_frame_index')}")
    lines.extend(f"blocker: {code}" for code in payload.get("blockers") or [])
    lines.extend(_wrote(payload))
    _finish(payload, lines, as_json)


@edit_pass_group.command("status")
@click.option("--job", required=True, help="Job id, output directory, or progress.json path.")
@click.option("--json", "as_json", is_flag=True, help="Print the progress JSON on stdout.")
def edit_pass_status_cmd(job: str, as_json: bool) -> None:
    """Read edit/progress.json for a job. Does not publish.

    \b
    Examples:
      fftf edit-pass status --job /tmp/ep05-edit
    """
    payload = run_edit_status(job)
    lines = [
        f"status: {payload.get('status')}",
        f"stage: {payload.get('stage')}",
    ]
    lines.extend(f"blocker: {code}" for code in payload.get("blockers") or [])
    _finish(payload, lines, as_json)


@main.group("distro")
def distro_group() -> None:
    """Distro runners. Dry-run default. Never live-publishes.

    Order: yt-long, then shorts (needs the long-form URL), then podcast.
    podcast-extended is a separate GO and is not part of that wave.
    Script, Verifier, and Frame have no Distro path.

    \b
    Examples:
      fftf distro status --pack /tmp/ep05-pack -o /tmp/ep05-distro
      fftf distro yt-long --pack /tmp/ep05-pack -o /tmp/ep05-distro
      fftf distro shorts --pack /tmp/ep05-pack --longform-url https://example.com/ep05 -o /tmp/ep05-distro
      fftf distro podcast --pack /tmp/ep05-pack -o /tmp/ep05-distro
    """


def _distro_finish(payload: dict, as_json: bool) -> None:
    lines = [
        f"runner: {payload.get('runner', 'status')}",
        f"ok: {str(payload.get('ok')).lower()}",
        f"dry-run: {str(payload.get('dry_run', True)).lower()}",
    ]
    lines.extend(f"blocker: {code}" for code in payload.get("blockers") or [])
    lines.extend(_wrote(payload))
    _finish(payload, lines, as_json)


@distro_group.command("status")
@click.option("--pack", required=True, type=click.Path(exists=True, path_type=Path), help="Frozen episode pack.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path))
@click.option("--allow-pwe", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def distro_status_cmd(pack: Path, out_dir: Path | None, allow_pwe: bool, as_json: bool) -> None:
    """Readiness report and size checklist. Never publishes.

    \b
    Examples:
      fftf distro status --pack /tmp/ep05-pack -o /tmp/ep05-distro
    """
    payload = _guard(lambda: run_distro_status(pack, out_dir=out_dir, allow_pwe=allow_pwe))
    _distro_finish(payload, as_json)


@distro_group.command("yt-long")
@click.option("--pack", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run/--apply", default=True, help="Dry-run is the default. --apply writes a local plan and does not upload.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path))
@click.option("--allow-pwe", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def distro_yt_long_cmd(pack: Path, dry_run: bool, out_dir: Path | None, allow_pwe: bool, as_json: bool) -> None:
    """YouTube long-form wave. First in order. Does not call YouTube.

    \b
    Examples:
      fftf distro yt-long --pack /tmp/ep05-pack -o /tmp/ep05-distro
    """
    payload = _guard(
        lambda: run_distro_yt_long(pack, apply=not dry_run, out_dir=out_dir, allow_pwe=allow_pwe)
    )
    _distro_finish(payload, as_json)


@distro_group.command("shorts")
@click.option("--pack", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--longform-url", default=None, help="Canonical long-form URL from yt-long. Required. Not fetched.")
@click.option("--dry-run/--apply", default=True, help="Dry-run is the default. --apply writes a local plan and does not upload.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path))
@click.option("--allow-pwe", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def distro_shorts_cmd(pack: Path, longform_url: str | None, dry_run: bool, out_dir: Path | None, allow_pwe: bool, as_json: bool) -> None:
    """Shorts A–D after yt-long. Hooks stay claim-gated. Does not call YouTube.

    \b
    Examples:
      fftf distro shorts --pack /tmp/ep05-pack --longform-url https://example.com/ep05 -o /tmp/ep05-distro
    """
    payload = _guard(
        lambda: run_distro_shorts(
            pack,
            longform_url=longform_url,
            apply=not dry_run,
            out_dir=out_dir,
            allow_pwe=allow_pwe,
        )
    )
    _distro_finish(payload, as_json)


@distro_group.command("podcast")
@click.option("--pack", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--dry-run/--apply", default=True, help="Dry-run is the default. --apply writes a local plan and does not upload.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path))
@click.option("--allow-pwe", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def distro_podcast_cmd(pack: Path, dry_run: bool, out_dir: Path | None, allow_pwe: bool, as_json: bool) -> None:
    """Podcast wave with a LOCKED cover and YT-length audio. Extended audio is not included.

    \b
    Examples:
      fftf distro podcast --pack /tmp/ep05-pack -o /tmp/ep05-distro
    """
    payload = _guard(
        lambda: run_distro_podcast(pack, apply=not dry_run, out_dir=out_dir, allow_pwe=allow_pwe)
    )
    _distro_finish(payload, as_json)


@distro_group.command("podcast-extended")
@click.option("--pack", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--go", "go_path", default=None, type=click.Path(path_type=Path), help="Separate Distro GO artifact. The main Distro GO is not enough.")
@click.option("--dry-run/--apply", default=True, help="Dry-run is the default. --apply writes a local plan and does not upload.")
@click.option("-o", "--out-dir", default=None, type=click.Path(path_type=Path))
@click.option("--allow-pwe", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
def distro_podcast_extended_cmd(pack: Path, go_path: Path | None, dry_run: bool, out_dir: Path | None, allow_pwe: bool, as_json: bool) -> None:
    """Optional extended podcast audio. Separate GO. Not part of the YT wave.

    \b
    Examples:
      fftf distro podcast-extended --pack /tmp/ep05-pack --go /tmp/ep05-pack/podcast-extended-go.json
    """
    payload = _guard(
        lambda: run_distro_podcast_extended(
            pack,
            go_path=go_path,
            apply=not dry_run,
            out_dir=out_dir,
            allow_pwe=allow_pwe,
        )
    )
    _distro_finish(payload, as_json)


if __name__ == "__main__":
    main()
