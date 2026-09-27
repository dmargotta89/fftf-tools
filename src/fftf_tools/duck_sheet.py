"""Parse CLIP-NOTES / CUT-AV-DUCK-CUES markdown into duck cue sheets."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

# MM:SS or HH:MM:SS, optional fractional seconds. Separators are dash, arrow, or "->".
_TC = r"\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?"
_SEP = r"\s*(?:[–—\-]|→|->)\s*"
TIME_RE = re.compile(rf"(?P<in>{_TC}){_SEP}(?P<out>{_TC})")
LEN_RE = re.compile(r"~?\s*(?P<sec>\d+(?:\.\d+)?)\s*s", re.I)
CLIP_HEADING_RE = re.compile(
    r"^##\s+(?:\d+[.)]\s*)?(?P<title>.+?)(?:\s*[—–-].*)?$",
    re.M,
)
PATH_RE = re.compile(
    r"(?:\*\*path\*\*\s*\|\s*`?([^`|\n]+?)`?(?:\s*\||$))|(?:[-*]\s*Path:\s*`?([^`\n]+?)`?\s*$)",
    re.I | re.M,
)
# Index lists and failure logs are not insert cues. A cue inside one of these
# headings is ignored so it is not glued onto the previous clip.
_META_HEADING_RE = re.compile(r"(?i)(failures|cut remux|remux order|recommended)")
_LIST_ITEM_RE = re.compile(r"^[\t ]*(?:[-*]|\d+[.)])\s+(?P<body>.+?)\s*$", re.M)


@dataclass
class DuckCue:
    clip: str
    in_tc: str
    out_tc: str
    duration_s: float
    label: str
    vo_pause_note: str = "pause VO under clip audio"
    source_path: str = ""


@dataclass
class ClipSection:
    clip: str
    source_path: str
    body: str
    start: int


def _tc_to_seconds(tc: str) -> float:
    parts = tc.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise ValueError(f"bad timecode: {tc}") from exc
    raise ValueError(f"bad timecode: {tc}")


def _clip_name_from_path(path: str) -> str:
    return Path(path).stem


def _heading_blocks(text: str) -> list[tuple[int, int, bool]]:
    """Return ``(start, end, skipped)`` for each ``##`` heading."""
    matches = list(re.finditer(r"^##\s+(.+)$", text, re.M))
    blocks: list[tuple[int, int, bool]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(1).strip()
        blocks.append((match.start(), end, bool(_META_HEADING_RE.search(title))))
    return blocks


def _in_skipped_heading(blocks: list[tuple[int, int, bool]], pos: int) -> bool:
    for start, end, skipped in blocks:
        if start <= pos < end:
            return skipped
    return False


def _sections_from_text(text: str) -> list[ClipSection]:
    sections: list[ClipSection] = []
    blocks = _heading_blocks(text)
    matches = list(re.finditer(r"^##\s+(.+)$", text, re.M))
    for match, (start, end, skipped) in zip(matches, blocks):
        if skipped:
            continue
        title = match.group(1).strip()
        body = text[match.end() : end]
        path_m = PATH_RE.search(body)
        path = ""
        if path_m:
            path = (path_m.group(1) or path_m.group(2) or "").strip().strip("`")
        clip = _clip_name_from_path(path) if path else re.sub(
            r"^\d+[.)]\s*", "", title
        )
        clip = re.sub(r"\s+", " ", clip).strip()
        sections.append(
            ClipSection(clip=clip, source_path=path, body=body, start=start)
        )
    return sections


def parse_clip_sections(path: Path | str) -> list[ClipSection]:
    """Section index shared with duck-cue parsing (clip, path, body)."""
    return _sections_from_text(Path(path).read_text(encoding="utf-8"))


def _current_clip_context(text: str) -> list[tuple[int, str, str]]:
    """Return list of (start_offset, clip_label, source_path) section starts."""
    return [(sec.start, sec.clip, sec.source_path) for sec in _sections_from_text(text)]


def _section_at(sections: list[tuple[int, str, str]], pos: int) -> tuple[str, str]:
    current = ("unknown", "")
    for start, clip, source_path in sections:
        if start <= pos:
            current = (clip, source_path)
        else:
            break
    return current


def _clip_at(sections: list[tuple[int, str, str]], pos: int) -> str:
    return _section_at(sections, pos)[0]


def _duration_seconds(in_tc: str, out_tc: str, length_text: str) -> float:
    match = LEN_RE.search(length_text) if length_text else None
    if match:
        return float(match.group("sec"))
    return max(0.0, _tc_to_seconds(out_tc) - _tc_to_seconds(in_tc))


def _clean_label(text: str) -> str:
    label = re.sub(r"\*\*", "", text)
    label = re.sub(r"^[\s*`]*", "", label)
    label = re.sub(r"^[—–\-:]+\s*", "", label)
    return re.sub(r"\s+", " ", label).strip()


def _span_from_body(body: str) -> tuple[str, str, float, str] | None:
    """Pull in/out, duration, and label from one list-item body."""
    match = TIME_RE.search(body)
    if not match:
        return None
    in_tc, out_tc = match.group("in"), match.group("out")
    after = body[match.end() :]
    length_match = re.match(
        r"\s*(?:\*\*)?\s*\((?P<len>~?\s*\d+(?:\.\d+)?\s*s)\)",
        after,
    )
    if length_match:
        duration = _duration_seconds(in_tc, out_tc, length_match.group("len"))
        after = after[length_match.end() :]
    else:
        nearby = LEN_RE.search(after)
        if nearby and nearby.start() <= 8:
            duration = float(nearby.group("sec"))
            after = after[: nearby.start()] + after[nearby.end() :]
        else:
            duration = _duration_seconds(in_tc, out_tc, "")
    return in_tc, out_tc, duration, _clean_label(after)


def _remember(
    cues: list[DuckCue],
    seen: set[tuple[str, str, str]],
    *,
    clip: str,
    source_path: str,
    in_tc: str,
    out_tc: str,
    duration_s: float,
    label: str,
) -> None:
    key = (clip, in_tc, out_tc)
    if key in seen:
        return
    seen.add(key)
    cues.append(
        DuckCue(
            clip=clip,
            in_tc=in_tc,
            out_tc=out_tc,
            duration_s=duration_s,
            label=label,
            source_path=source_path,
        )
    )


def parse_duck_cues(path: Path | str) -> list[DuckCue]:
    path = Path(path)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    sections = _current_clip_context(text)
    skipped = _heading_blocks(text)
    cues: list[DuckCue] = []
    seen: set[tuple[str, str, str]] = set()

    # Style A: markdown table rows | **03:18–03:32** | **~14s** | label |
    # Also accepts arrows (03:18→03:32, 03:18->03:32) and fractional seconds.
    table_row = re.compile(
        r"^\|\s*\*?\*?(?P<span>[^|]+?)\*?\*?\s*\|\s*\*?\*?(?P<length>[^|]+?)\*?\*?\s*\|\s*(?P<label>[^|]+?)\s*\|",
        re.M,
    )
    for match in table_row.finditer(text):
        if _in_skipped_heading(skipped, match.start()):
            continue
        span = TIME_RE.search(match.group("span"))
        if not span:
            continue
        in_tc, out_tc = span.group("in"), span.group("out")
        clip, source_path = _section_at(sections, match.start())
        _remember(
            cues,
            seen,
            clip=clip,
            source_path=source_path,
            in_tc=in_tc,
            out_tc=out_tc,
            duration_s=_duration_seconds(in_tc, out_tc, match.group("length")),
            label=_clean_label(match.group("label")),
        )

    # Style B: list items. Bold is optional. Duration may sit inside or after the span.
    #   - **03:18–03:32 (~14s)** — label
    #   - **03:18–03:32** (~14s) — label
    #   - 01:20->01:34 (~14s) — label
    # Numbered remux indexes under a skipped heading are not cues.
    for match in _LIST_ITEM_RE.finditer(text):
        if _in_skipped_heading(skipped, match.start()):
            continue
        parsed = _span_from_body(match.group("body"))
        if parsed is None:
            continue
        in_tc, out_tc, duration_s, label = parsed
        clip, source_path = _section_at(sections, match.start())
        _remember(
            cues,
            seen,
            clip=clip,
            source_path=source_path,
            in_tc=in_tc,
            out_tc=out_tc,
            duration_s=duration_s,
            label=label,
        )

    return cues


def write_duck_sheets(
    cues: list[DuckCue],
    out_prefix: Path | str,
) -> tuple[Path, Path]:
    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_prefix.with_suffix(".csv") if out_prefix.suffix == "" else Path(
        str(out_prefix) + ".csv"
    )
    md_path = out_prefix.with_suffix(".md") if out_prefix.suffix == "" else Path(
        str(out_prefix) + ".md"
    )
    # Prefer OUT_PREFIX.csv literally when user passes prefix without suffix
    if out_prefix.suffix not in {".csv", ".md"}:
        csv_path = Path(f"{out_prefix}.csv")
        md_path = Path(f"{out_prefix}.md")

    fieldnames = ["clip", "in", "out", "duration_s", "label", "vo_pause_note"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in cues:
            w.writerow(
                {
                    "clip": c.clip,
                    "in": c.in_tc,
                    "out": c.out_tc,
                    "duration_s": f"{c.duration_s:.1f}",
                    "label": c.label,
                    "vo_pause_note": c.vo_pause_note,
                }
            )

    lines = [
        "# Duck cue sheet",
        "",
        "| clip | in | out | duration_s | label | vo_pause_note |",
        "|---|---|---|---|---|---|",
    ]
    for c in cues:
        label = c.label.replace("|", "\\|")
        lines.append(
            f"| {c.clip} | {c.in_tc} | {c.out_tc} | {c.duration_s:.1f} | "
            f"{label} | {c.vo_pause_note} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path, md_path


def run_duck_sheet(
    clip_notes: Path | str,
    vo_timing: Path | str | None = None,
    out_prefix: Path | str = "duck-cues",
) -> tuple[Path, Path]:
    cues = parse_duck_cues(clip_notes)
    # Optional VO timing currently unused for cue extraction; reserved for
    # future pause-alignment notes. Accept path to keep CLI stable.
    _ = vo_timing
    csv_path, md_path = write_duck_sheets(cues, out_prefix)
    print(f"wrote {csv_path} ({len(cues)} cues)")
    print(f"wrote {md_path}")
    return csv_path, md_path
