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
from fftf_tools.drive_checklist import write_drive_checklist
from fftf_tools.duck_sheet import run_duck_sheet
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
    """Validate VO-timing markdown (exit 0 PASS / 1 FAIL)."""
    code = run_vo_check(path, min_min=min_min, max_min=max_min)
    sys.exit(code)


@main.command("duck-sheet")
@click.argument("clip_notes", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--vo", "vo_timing", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Optional VO-timing file.")
@click.option("-o", "out_prefix", default="duck-cues", show_default=True, help="Output prefix for .csv and .md.")
def duck_sheet_cmd(clip_notes: Path, vo_timing: Path | None, out_prefix: str) -> None:
    """Parse CLIP-NOTES / duck-cues markdown; emit CSV + MD cue sheets."""
    run_duck_sheet(clip_notes, vo_timing=vo_timing, out_prefix=out_prefix)


@main.command("drive-checklist")
@click.option("--ep", required=True, type=int, help="Episode number.")
@click.option("--title", required=True, type=str, help="Episode title.")
@click.option("-o", "out_file", default=None, type=click.Path(path_type=Path), help="Output markdown file.")
def drive_checklist_cmd(ep: int, title: str, out_file: Path | None) -> None:
    """Write a Drive episode checklist markdown."""
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
    """Draw thumbnail safe-zone overlay; warn if not 1280x720."""
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
    """Write a local Studio paste pack. Does not upload or unlock Distro."""
    run_distro_pack(
        ep=ep,
        title=title,
        draft=draft,
        vo_timing=vo_timing,
        thumb=thumb,
        out_dir=out_dir,
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
    """Write a 4-cut Shorts bake brief. Does not render video."""
    run_shorts_cutter(
        ep=ep,
        vo_timing=vo_timing,
        clip_notes=clip_notes,
        title=title,
        out_dir=out_dir,
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
    """Write a verifier report. Exit 1 on FAIL. Distro stays blocked."""
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


if __name__ == "__main__":
    main()
