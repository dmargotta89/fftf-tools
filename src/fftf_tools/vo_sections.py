"""Parse FFTF VO-timing / narration markdown into sections.

Timing uses the same pause table as ``vo_check`` so chapter estimates
stay aligned with the duration check. Nothing here contacts a platform.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fftf_tools.machine import BASE_FENCES
from fftf_tools.vo_check import MARKER_RE, PAUSE_DUR, WORDS_PER_MIN

NARRATION_HEADING_RE = re.compile(
    r"(?i)^(cold open|channel intro|act\s+\d+\b|mid-?roll|cta\b)"
)
URL_RE = re.compile(r"https?://[^\s)>\]]+")
FENCE_LINE_RE = re.compile(
    r"(?i)(do not publish|do not distro|no distro|will not treat|"
    r"what we refuse|do not invent|not treat as proven)"
)


@dataclass
class VoSection:
    heading: str
    heading_line: int
    body: str
    first_spoken_line: int | None
    hook_end_line: int | None

    @property
    def plain(self) -> str:
        return spoken_plain(self.body)


def spoken_plain(text: str) -> str:
    """Strip pause markers and emphasis. Does not add words."""
    out = re.sub(r"\[(?:br|p|P)\]", " ", text)
    out = out.replace("|", " ")
    out = re.sub(r"[*_`]", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries. Keep initials such as ``v.`` attached."""
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    merged: list[str] = []
    buf = ""
    for part in parts:
        if not buf:
            buf = part
            continue
        if re.search(r"(?:^|\s)[A-Za-z]\.$", buf):
            buf = f"{buf} {part}"
            continue
        merged.append(buf)
        buf = part
    if buf:
        merged.append(buf)
    return merged


def first_sentences(text: str, n: int = 1, limit: int = 320) -> str:
    text = text.strip()
    if not text:
        return ""
    parts = split_sentences(text)
    out = " ".join(parts[:n]).strip()
    if len(out) <= limit:
        return out
    if parts and len(parts[0]) <= limit:
        return parts[0]
    return out[: limit - 1].rstrip() + "…"


def _count_words(stripped: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", stripped))


def section_seconds(body: str) -> float:
    counts = {k: 0 for k in PAUSE_DUR}
    for match in MARKER_RE.finditer(body):
        tok = match.group(0)
        if tok in counts:
            counts[tok] += 1
    words = _count_words(spoken_plain(body))
    speech_s = (words / WORDS_PER_MIN) * 60.0 if words else 0.0
    pause_s = sum(counts[k] * PAUSE_DUR[k] for k in PAUSE_DUR)
    return speech_s + pause_s


def is_narration_heading(heading: str) -> bool:
    return bool(NARRATION_HEADING_RE.match(heading.strip()))


def parse_sections(text: str) -> list[VoSection]:
    """Return narration sections (cold open, acts, mid-roll, CTA)."""
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match and is_narration_heading(match.group(1)):
            headings.append((i, match.group(1).strip()))

    sections: list[VoSection] = []
    for idx, (start, heading) in enumerate(headings):
        end = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        # Stop early at production notes that follow the close.
        for j in range(start + 1, end):
            if re.match(r"^##\s+", lines[j]):
                end = j
                break
        body_lines = lines[start + 1 : end]
        body = "\n".join(body_lines)
        first_spoken = None
        hook_end = None
        for offset, line in enumerate(body_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or re.match(r"^---+$", stripped):
                continue
            if first_spoken is None:
                first_spoken = start + 2 + offset  # 1-based
            if first_spoken is not None and re.search(r"[.!?]", spoken_plain(line)):
                hook_end = start + 2 + offset
                break
        if first_spoken is not None and hook_end is None:
            hook_end = first_spoken
        sections.append(
            VoSection(
                heading=heading,
                heading_line=start + 1,
                body=body,
                first_spoken_line=first_spoken,
                hook_end_line=hook_end,
            )
        )
    return sections


def chapter_label(heading: str) -> str:
    raw = re.sub(r"\s*\([^)]*\)", "", heading).strip()
    raw = re.sub(r"\s+", " ", raw)
    upper = raw.upper()
    if upper.startswith("COLD OPEN"):
        return "Cold open"
    if upper.startswith("CHANNEL INTRO"):
        return "Channel intro"
    if upper.startswith("MID-ROLL") or upper.startswith("MIDROLL"):
        return "Mid-roll"
    if upper.startswith("CTA"):
        return "CTA"
    match = re.match(r"ACT\s+(\d+)\s*[—–-]?\s*(.*)$", raw, re.I)
    if match:
        rest = match.group(2).strip(" —–-")
        if rest:
            rest_label = rest[:1].upper() + rest[1:].lower()
            return f"Act {match.group(1)} — {rest_label}"
        return f"Act {match.group(1)}"
    if not raw:
        return "Section"
    return raw[:1].upper() + raw[1:].lower()


def format_timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def chapter_lines(sections: list[VoSection]) -> list[str]:
    """YouTube-style chapter lines. First entry is always 0:00."""
    if not sections:
        return []
    cursor = 0.0
    stamped: list[tuple[float, str]] = []
    for section in sections:
        stamped.append((cursor, chapter_label(section.heading)))
        cursor += section_seconds(section.body)
    lines: list[str] = []
    last = -1
    for i, (sec, label) in enumerate(stamped):
        val = 0 if i == 0 else int(round(sec))
        if val <= last:
            val = last + 1
        last = val
        lines.append(f"{format_timestamp(val)} {label}")
    return lines


def estimated_duration_seconds(sections: list[VoSection]) -> float:
    return sum(section_seconds(section.body) for section in sections)


def extract_sources(text: str, origin: str) -> list[dict]:
    """Copy locators that already appear in ``text``. Never invent one."""
    sources: list[dict] = []
    seen: set[str] = set()
    for match in URL_RE.finditer(text):
        locator = match.group(0).rstrip(".,;")
        if locator in seen:
            continue
        seen.add(locator)
        sources.append(
            {
                "id": f"s{len(sources) + 1}",
                "locator": locator,
                "label": "mentioned in input",
                "origin": origin,
                "verified": False,
            }
        )
    return sources


def renumber_sources(sources: list[dict]) -> list[dict]:
    out = []
    seen: set[str] = set()
    for source in sources:
        locator = source.get("locator", "")
        if locator in seen:
            continue
        seen.add(locator)
        item = dict(source)
        item["id"] = f"s{len(out) + 1}"
        item["verified"] = False
        out.append(item)
    return out


def _fence_chunks(line: str) -> list[str]:
    """Return fence text already on this line, split only when it is long."""
    plain = spoken_plain(line).strip(" -")
    if not plain or not FENCE_LINE_RE.search(plain):
        return []
    if len(plain) <= 300:
        return [plain]
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", plain) if part.strip()]
    chunks: list[str] = []
    for index, sentence in enumerate(sentences):
        if not FENCE_LINE_RE.search(sentence):
            continue
        chunk = sentence
        if len(sentence) < 80 and index > 0:
            chunk = f"{sentences[index - 1]} {sentence}"
        chunks.append(chunk)
    return chunks


def extract_fences(text: str, origin: str) -> list[dict]:
    """Copy fence sentences already written in the input."""
    fences: list[dict] = []
    seen: set[str] = set()
    for i, line in enumerate(text.splitlines(), 1):
        for cleaned in _fence_chunks(line):
            if cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            fences.append(
                {
                    "id": f"{origin}-{len(fences) + 1}",
                    "text": cleaned,
                    "locked": True,
                    "origin": f"{origin}:L{i}",
                }
            )
            if len(fences) >= 8:
                return fences
    return fences


def merge_fences(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = [dict(item) for item in BASE_FENCES]
    seen = {item["text"].lower() for item in merged}
    for group in groups:
        for item in group:
            key = item.get("text", "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(dict(item))
    return merged
