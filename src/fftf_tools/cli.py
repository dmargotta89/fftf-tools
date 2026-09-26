"""fftf CLI — From Fiction to Fact production helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from fftf_tools.distro_pack import run_distro_pack
from fftf_tools.drive_checklist import write_drive_checklist
from fftf_tools.duck_sheet import run_duck_sheet
from fftf_tools.shorts_cutter import run_shorts_cutter
from fftf_tools.thumb_safe import draw_thumb_safe
from fftf_tools.vo_check import run_vo_check


@click.group()
@click.version_option(package_name="fftf-tools")
def main() -> None:
    """From Fiction to Fact (FFTF) production helpers."""


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


if __name__ == "__main__":
    main()
