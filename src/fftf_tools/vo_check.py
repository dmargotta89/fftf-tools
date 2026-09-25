"""Validate VO-timing markdown for FFTF production."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MARKER_RE = re.compile(r"\[br\]|\[p\]|\[P\]|\|")
# Classic mid-clause: word/emphasis char, optional space, [br], optional space, word
WORD_BR_WORD_RE = re.compile(r"[A-Za-z0-9*]\s*\[br\]\s*[A-Za-z0-9*]")
PAUSE_DUR = {
    "[br]": 0.25,
    "[p]": 0.80,
    "[P]": 1.35,
}
WORDS_PER_MIN = 160.0

BODY_START_RE = re.compile(
    r"^##\s+(COLD OPEN|CHANNEL INTRO|ACT\s+\d|Full narration)",
    re.I,
)
BODY_END_RE = re.compile(
    r"^##\s+(Cut notes|Marker counts|Self-check)",
    re.I,
)


@dataclass
class VoCheckResult:
    ok: bool
    notes: list[str] = field(default_factory=list)
    duration_min: float | None = None
    word_count: int = 0
    marker_counts: dict[str, int] = field(default_factory=dict)

    def summary_lines(self) -> list[str]:
        lines = []
        status = "PASS" if self.ok else "FAIL"
        lines.append(f"vo-check: {status}")
        if self.duration_min is not None:
            lines.append(f"estimated_duration_min: {self.duration_min:.2f}")
        lines.append(f"spoken_word_count: {self.word_count}")
        if self.marker_counts:
            counts = ", ".join(f"{k}={v}" for k, v in sorted(self.marker_counts.items()))
            lines.append(f"markers: {counts}")
        lines.extend(self.notes)
        return lines


def _strip_markers(text: str) -> str:
    out = MARKER_RE.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


def _body_line_range(lines: list[str]) -> tuple[int | None, int | None]:
    """1-based inclusive start, exclusive end of narration body headings."""
    start = None
    end = None
    for i, line in enumerate(lines, 1):
        if start is None and BODY_START_RE.match(line):
            start = i
        if start is not None and BODY_END_RE.match(line):
            end = i
            break
    return start, end


def _spoken_body(lines: list[str]) -> str:
    start, end = _body_line_range(lines)
    if start is None:
        return "\n".join(lines)
    chunk = lines[start - 1 : (end - 1) if end else None]
    keep = []
    for ln in chunk:
        if re.match(r"^#{1,6}\s", ln) or re.match(r"^---+$", ln.strip()):
            continue
        keep.append(ln)
    return "\n".join(keep)


def _count_words(stripped: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", stripped))


def _has_header(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.I | re.M))


def _section_nonempty(text: str, header_pat: str) -> bool:
    m = re.search(header_pat, text, re.I | re.M)
    if not m:
        return False
    rest = text[m.end() :]
    next_h = re.search(r"^##\s+", rest, re.M)
    body = rest[: next_h.start()] if next_h else rest
    return bool(body.strip())


def validate_vo_timing(
    path: Path | str,
    min_min: float = 8.0,
    max_min: float = 12.0,
) -> VoCheckResult:
    path = Path(path)
    notes: list[str] = []
    ok = True
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- strip / format consistency ---
    for i, line in enumerate(lines, 1):
        for m in re.finditer(r"\[[^\]]*\]", line):
            tok = m.group(0)
            if tok not in ("[br]", "[p]", "[P]") and re.match(
                r"\[(br|p|P|pause|break)", tok, re.I
            ):
                ok = False
                notes.append(f"L{i}: unexpected marker/format '{tok}'")
        if "|||" in line:
            ok = False
            notes.append(f"L{i}: unexpected marker/format '|||'")

    # --- mid-clause chop patterns (narration body only) ---
    body_start, body_end = _body_line_range(lines)
    for i, line in enumerate(lines, 1):
        if body_start is not None:
            if i < body_start:
                continue
            if body_end is not None and i >= body_end:
                continue
        if re.match(r"^#{1,6}\s", line) or re.match(r"^---+$", line.strip()):
            continue
        if WORD_BR_WORD_RE.search(line):
            ok = False
            notes.append(f"L{i}: mid-clause [br] chop pattern")

    # --- density / notes sections when headers exist ---
    if _has_header(text, r"^##\s+Marker counts"):
        if not _section_nonempty(text, r"^##\s+Marker counts"):
            ok = False
            notes.append("Marker counts section present but empty")
        sec = re.search(
            r"^##\s+Marker counts.*?(?=^##\s|\Z)", text, re.I | re.M | re.S
        )
        if sec and not re.search(r"\[p\]|\[P\]|\[br\]", sec.group(0)):
            ok = False
            notes.append("Marker counts section missing marker tallies")

    if _has_header(text, r"(?i)\*\*Density:\*\*|^##\s+.*[Dd]ensity"):
        if not re.search(r"(?i)Density:\s*.{10,}", text):
            ok = False
            notes.append("Density header/label present but content missing")

    if _has_header(text, r"^##\s+Cut notes"):
        if not _section_nonempty(text, r"^##\s+Cut notes"):
            ok = False
            notes.append("Cut notes section present but empty")

    if _has_header(text, r"^##\s+Self-check"):
        if not _section_nonempty(text, r"^##\s+Self-check"):
            ok = False
            notes.append("Self-check section present but empty")

    # --- marker counts & duration estimate ---
    body = _spoken_body(lines)
    counts = {"[br]": 0, "[p]": 0, "[P]": 0, "|": 0}
    for m in MARKER_RE.finditer(body):
        counts[m.group(0)] = counts.get(m.group(0), 0) + 1

    stripped = _strip_markers(body)
    word_count = _count_words(stripped)
    speech_min = word_count / WORDS_PER_MIN if word_count else 0.0
    pause_s = sum(counts.get(k, 0) * PAUSE_DUR[k] for k in PAUSE_DUR)
    duration_min = speech_min + pause_s / 60.0

    if word_count == 0:
        ok = False
        notes.append("could not parse spoken body / word count is 0")
    else:
        if duration_min < min_min:
            ok = False
            notes.append(
                f"duration {duration_min:.2f} min below --min-min {min_min}"
            )
        elif duration_min > max_min:
            ok = False
            notes.append(
                f"duration {duration_min:.2f} min above --max-min {max_min}"
            )
        else:
            notes.append(
                f"duration {duration_min:.2f} min within [{min_min}, {max_min}]"
            )

    if not any("mid-clause" in n for n in notes):
        notes.append("no mid-clause [br] chop patterns detected")

    notes.append("strip/format markers look consistent")

    return VoCheckResult(
        ok=ok,
        notes=notes,
        duration_min=duration_min if word_count else None,
        word_count=word_count,
        marker_counts=counts,
    )


def run_vo_check(
    path: Path | str,
    min_min: float = 8.0,
    max_min: float = 12.0,
) -> int:
    result = validate_vo_timing(path, min_min=min_min, max_min=max_min)
    for line in result.summary_lines():
        print(line)
    return 0 if result.ok else 1
