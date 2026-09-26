"""Write a local YouTube description pack. Does not upload or unlock Distro."""

from __future__ import annotations

import re
from pathlib import Path

from fftf_tools.machine import (
    CHANNEL_NAME,
    CHANNEL_SHORT,
    episode_id_for,
    machine_block,
    write_machine_json,
)
from fftf_tools.vo_sections import (
    chapter_lines,
    extract_fences,
    extract_sources,
    first_sentences,
    merge_fences,
    parse_sections,
    renumber_sources,
)

LONG_FORM_URL = "{{LONG_FORM_URL}}"
SOURCE_PLACEHOLDER = "[ ] PRIMARY SOURCE PLACEHOLDER"

_STOP_TAGS = {
    "the",
    "and",
    "for",
    "from",
    "with",
    "that",
    "this",
    "episode",
    "into",
    "over",
}


def build_title(ep: int, title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    line = f"{title} | {CHANNEL_NAME} Ep {ep:02d}"
    if len(line) <= 100:
        return line
    budget = 100 - len(f" | {CHANNEL_NAME} Ep {ep:02d}")
    trimmed = title[: max(budget, 1)].rstrip()
    return f"{trimmed} | {CHANNEL_NAME} Ep {ep:02d}"


def build_tags(ep: int, title: str) -> list[str]:
    tags = [CHANNEL_NAME, CHANNEL_SHORT, f"Episode {ep:02d}"]
    seen = {tag.lower() for tag in tags}
    for word in re.findall(r"[A-Za-z0-9']+", title):
        if word.lower() in _STOP_TAGS or word.lower() in seen:
            continue
        if len(word) < 3:
            continue
        tags.append(word)
        seen.add(word.lower())
    return tags


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cold_open_quote(texts: list[str]) -> str:
    for text in texts:
        for section in parse_sections(text):
            if section.heading.lower().startswith("cold open"):
                quote = first_sentences(section.plain, n=2, limit=400)
                if quote:
                    return quote
    return ""


def _cta_quote(texts: list[str]) -> str:
    for text in texts:
        for section in parse_sections(text):
            if section.heading.lower().startswith("cta"):
                quote = first_sentences(section.plain, n=2, limit=400)
                if quote:
                    return quote
    return ""


def build_description(
    *,
    ep: int,
    title: str,
    cold_open: str,
    cta: str,
    thumb: str | None,
    chapters_estimated: bool,
) -> str:
    if cold_open:
        hook = (
            "Quoted from the supplied draft (markers stripped). Not a new claim.\n\n"
            f"> {cold_open}"
        )
    else:
        hook = "(No cold-open section in the supplied draft. Do not invent a hook.)"
    if cta:
        cta_block = (
            "Quoted from the supplied draft CTA when one was present.\n\n"
            f"> {cta}"
        )
    else:
        cta_block = (
            f"This was {CHANNEL_NAME}. "
            "Subscribe only after a human pastes this pack. "
            "Do not add a claim that is not in the stamped draft."
        )
    thumb_line = thumb if thumb else "(none supplied)"
    chapter_note = (
        "Times in CHAPTERS.txt are estimates from VO-timing markup "
        "(160 words/min plus pause markers), not a picture-lock timeline. "
        "Check them before any Studio paste."
        if chapters_estimated
        else "No VO-timing section headers were available. "
        "CHAPTERS.txt contains only a 0:00 title line. Do not invent timestamps."
    )
    lines = [
        f"# {CHANNEL_NAME} ({CHANNEL_SHORT}) — Episode {ep:02d}",
        "",
        title,
        "",
        "DO NOT UPLOAD. This pack does not unlock Distro and does not publish.",
        "distro_blocked: true",
        "",
        "Channel display name: From Fiction to Fact (FFTF).",
        "",
        "## Cold open hook",
        "",
        hook,
        "",
        "## Chapters",
        "",
        chapter_note,
        "",
        "## Sources",
        "",
        "Placeholders only. This pack does not invent primary sources.",
        "Replace a placeholder only with a source already named in the stamped draft.",
        "",
        SOURCE_PLACEHOLDER,
        SOURCE_PLACEHOLDER,
        SOURCE_PLACEHOLDER,
        "",
        "## CTA",
        "",
        cta_block,
        "",
        f"Subscribe to {CHANNEL_NAME}.",
        "",
        "## Shorts",
        "",
        "Caption templates are in SHORTS-CAPTIONS.md.",
        f"Long-form URL placeholder: {LONG_FORM_URL}",
        "",
        "## Local assets",
        "",
        f"Thumb path (recorded only, not uploaded): {thumb_line}",
        "",
    ]
    return "\n".join(lines)


def build_shorts_captions(
    *,
    ep: int,
    title: str,
    hooks: dict[str, str],
) -> str:
    labels = {
        "A": "Cold open",
        "B": "The fiction",
        "C": "The reveal",
        "D": "Aftermath and close",
    }
    lines = [
        f"# Shorts captions A–D — Ep {ep:02d} {title}",
        "",
        f"Channel: {CHANNEL_NAME} ({CHANNEL_SHORT})",
        "distro_blocked: true",
        "Templates for a human to paste. This file does not upload.",
        f"Long-form URL placeholder: {LONG_FORM_URL}",
        "",
    ]
    for key in ("A", "B", "C", "D"):
        hook = hooks.get(key) or "(No matching line in the supplied draft. Do not invent one.)"
        lines.extend(
            [
                f"## {key} — {labels[key]}",
                "",
                hook,
                "",
                f"Full episode: {LONG_FORM_URL}",
                "",
                f"{CHANNEL_NAME} ({CHANNEL_SHORT})",
                "",
            ]
        )
    return "\n".join(lines)


def _hook_for(prefix: str, texts: list[str]) -> str:
    for text in texts:
        for section in parse_sections(text):
            if section.heading.lower().startswith(prefix):
                return first_sentences(section.plain, n=2, limit=280)
    return ""


def _chapters_text(vo_text: str | None, title: str) -> tuple[str, bool]:
    if vo_text:
        sections = parse_sections(vo_text)
        lines = chapter_lines(sections)
        if lines:
            return "\n".join(lines) + "\n", True
    safe_title = re.sub(r"\s+", " ", title).strip() or "Episode"
    return f"0:00 {safe_title}\n", False


def run_distro_pack(
    *,
    ep: int,
    title: str,
    draft: Path | str,
    vo_timing: Path | str | None = None,
    thumb: Path | str | None = None,
    out_dir: Path | str | None = None,
) -> dict:
    """Write distro/epXX pack files and machine JSON. Does not upload."""
    draft = Path(draft)
    vo_path = Path(vo_timing) if vo_timing else None
    episode_id = episode_id_for(ep)
    out = Path(out_dir) if out_dir else Path("distro") / episode_id
    out.mkdir(parents=True, exist_ok=True)

    draft_text = _read(draft)
    vo_text = _read(vo_path) if vo_path else None
    # Chapters come from VO-timing when that file is present; otherwise from
    # the draft if it already carries the same section headers.
    chapter_source = vo_text if vo_text is not None else draft_text
    chapters, estimated = _chapters_text(chapter_source, title)

    texts = [draft_text] + ([vo_text] if vo_text else [])
    hooks = {
        "A": _hook_for("cold open", texts),
        "B": _hook_for("act 1", texts),
        "C": _hook_for("act 3", texts) or _hook_for("act 2", texts),
        "D": _hook_for("act 4", texts) or _hook_for("cta", texts),
    }
    cold_open = _cold_open_quote(texts)
    cta = _cta_quote(texts)
    thumb_s = str(thumb) if thumb else None

    title_line = build_title(ep, title)
    description = build_description(
        ep=ep,
        title=title,
        cold_open=cold_open,
        cta=cta,
        thumb=thumb_s,
        chapters_estimated=estimated,
    )
    tags = "\n".join(build_tags(ep, title)) + "\n"
    captions = build_shorts_captions(ep=ep, title=title, hooks=hooks)

    files = {
        "TITLE.txt": title_line + "\n",
        "DESCRIPTION.md": description,
        "TAGS.txt": tags,
        "CHAPTERS.txt": chapters,
        "SHORTS-CAPTIONS.md": captions,
    }
    written: dict[str, Path] = {}
    for name, body in files.items():
        path = out / name
        path.write_text(body, encoding="utf-8")
        written[name] = path

    sources = renumber_sources(
        extract_sources(draft_text, str(draft))
        + (extract_sources(vo_text, str(vo_path)) if vo_text and vo_path else [])
    )
    fences = merge_fences(
        extract_fences(draft_text, "draft"),
        extract_fences(vo_text, "vo") if vo_text else [],
    )

    asset_index = [
        {"role": "draft", "path": str(draft)},
    ]
    if vo_path:
        asset_index.append({"role": "vo-timing", "path": str(vo_path)})
    if thumb_s:
        asset_index.append({"role": "thumb", "path": thumb_s, "note": "not uploaded"})
    roles = {
        "TITLE.txt": "yt-title",
        "DESCRIPTION.md": "yt-description",
        "TAGS.txt": "yt-tags",
        "CHAPTERS.txt": "yt-chapters",
        "SHORTS-CAPTIONS.md": "shorts-captions",
    }
    for name in files:
        asset_index.append({"role": roles[name], "path": name})
    asset_index.append({"role": "machine", "path": "machine.json"})

    block = machine_block(
        episode_id=episode_id,
        sources=sources,
        fences=fences,
        asset_index=asset_index,
        tool="distro-pack",
        channel=CHANNEL_NAME,
        channel_short=CHANNEL_SHORT,
        chapters_estimated=estimated,
        uploads=False,
    )
    machine_path = write_machine_json(out / "machine.json", block)
    written["machine.json"] = machine_path

    for name, path in written.items():
        print(f"wrote {path}")
    if estimated:
        print("CHAPTERS.txt times are estimates from VO-timing markup, not a bake timeline")
    else:
        print("CHAPTERS.txt has no estimated times (no VO-timing section headers)")
    print("distro_blocked: true")
    print("no upload; human/Cut pastes into Studio")
    return {"out_dir": out, "files": written, "machine": block}
