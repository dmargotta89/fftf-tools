"""Parse CLIP-NOTES / CUT-AV-DUCK-CUES markdown into duck cue sheets."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

TIME_RE = re.compile(
    r"(?P<in>\d{1,2}:\d{2}(?::\d{2})?)\s*[–—-]\s*(?P<out>\d{1,2}:\d{2}(?::\d{2})?)"
)
LEN_RE = re.compile(r"~?\s*(?P<sec>\d+(?:\.\d+)?)\s*s", re.I)
CLIP_HEADING_RE = re.compile(
    r"^##\s+(?:\d+[.)]\s*)?(?P<title>.+?)(?:\s*[—–-].*)?$",
    re.M,
)
PATH_RE = re.compile(
    r"(?:\*\*path\*\*\s*\|\s*`([^`]+)`)|(?:[-*]\s*Path:\s*`([^`]+)`)",
    re.I,
)


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
    parts = [int(p) for p in tc.split(":")]
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    raise ValueError(f"bad timecode: {tc}")


def _clip_name_from_path(path: str) -> str:
    return Path(path).stem


def _sections_from_text(text: str) -> list[ClipSection]:
    sections: list[ClipSection] = []
    for match in re.finditer(r"^##\s+(.+)$", text, re.M):
        title = match.group(1).strip()
        # skip meta sections
        if re.match(
            r"(?i)(failures|cut remux|remux order|recommended)",
            title,
        ):
            continue
        nxt = re.search(r"^##\s+", text[match.end() :], re.M)
        body = text[match.end() : match.end() + (nxt.start() if nxt else len(text))]
        path_m = PATH_RE.search(body)
        path = ""
        if path_m:
            path = path_m.group(1) or path_m.group(2) or ""
        clip = _clip_name_from_path(path) if path else re.sub(
            r"^\d+[.)]\s*", "", title
        )
        clip = re.sub(r"\s+", " ", clip).strip()
        sections.append(
            ClipSection(clip=clip, source_path=path, body=body, start=match.start())
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


def parse_duck_cues(path: Path | str) -> list[DuckCue]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    sections = _current_clip_context(text)
    cues: list[DuckCue] = []
    seen: set[tuple[str, str, str]] = set()

    # Style A: markdown table rows | **03:18–03:32** | **~14s** | label |
    table_row = re.compile(
        r"^\|\s*\*?\*?("
        r"\d{1,2}:\d{2}(?::\d{2})?\s*[–—-]\s*\d{1,2}:\d{2}(?::\d{2})?"
        r")\*?\*?\s*\|\s*\*?\*?([^|]+?)\*?\*?\s*\|\s*([^|]+?)\s*\|",
        re.M,
    )
    for m in table_row.finditer(text):
        span = m.group(1)
        len_cell = m.group(2).strip()
        label = re.sub(r"\*\*", "", m.group(3)).strip()
        tm = TIME_RE.search(span)
        if not tm:
            continue
        in_tc, out_tc = tm.group("in"), tm.group("out")
        lm = LEN_RE.search(len_cell)
        if lm:
            dur = float(lm.group("sec"))
        else:
            dur = max(0.0, _tc_to_seconds(out_tc) - _tc_to_seconds(in_tc))
        clip, source_path = _section_at(sections, m.start())
        key = (clip, in_tc, out_tc)
        if key in seen:
            continue
        seen.add(key)
        cues.append(
            DuckCue(
                clip=clip,
                in_tc=in_tc,
                out_tc=out_tc,
                duration_s=dur,
                label=label,
                source_path=source_path,
            )
        )

    # Style B: bullet  - **03:18–03:32 (~14s)** — label
    bullet = re.compile(
        r"^[\t ]*[-*]\s+\*\*"
        r"(?P<span>\d{1,2}:\d{2}(?::\d{2})?\s*[–—-]\s*\d{1,2}:\d{2}(?::\d{2})?)"
        r"(?:\s*\((?P<len>~?\s*\d+(?:\.\d+)?\s*s)\))?"
        r"\*\*"
        r"(?:\s*[—–-]\s*(?P<label>.+))?$",
        re.M,
    )
    for m in bullet.finditer(text):
        tm = TIME_RE.search(m.group("span"))
        if not tm:
            continue
        in_tc, out_tc = tm.group("in"), tm.group("out")
        len_raw = m.group("len") or ""
        lm = LEN_RE.search(len_raw) if len_raw else None
        if lm:
            dur = float(lm.group("sec"))
        else:
            dur = max(0.0, _tc_to_seconds(out_tc) - _tc_to_seconds(in_tc))
        label = (m.group("label") or "").strip()
        label = re.sub(r"\*\*", "", label)
        clip, source_path = _section_at(sections, m.start())
        key = (clip, in_tc, out_tc)
        if key in seen:
            continue
        seen.add(key)
        cues.append(
            DuckCue(
                clip=clip,
                in_tc=in_tc,
                out_tc=out_tc,
                duration_s=dur,
                label=label,
                source_path=source_path,
            )
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
