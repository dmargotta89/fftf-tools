"""Write a 4-cut Shorts bake brief. Does not render video or unlock Distro."""

from __future__ import annotations

import re
from pathlib import Path

from fftf_tools.duck_sheet import parse_duck_cues
from fftf_tools.machine import (
    CHANNEL_NAME,
    CHANNEL_SHORT,
    episode_id_for,
    machine_block,
)
from fftf_tools.schema import write_machine
from fftf_tools.vo_sections import (
    VoSection,
    extract_fences,
    extract_sources,
    first_sentences,
    merge_fences,
    parse_sections,
    renumber_sources,
)

LONG_FORM_URL = "{{LONG_FORM_URL}}"
NINE_SIXTEEN = (
    "9:16 vertical (1080×1920). Keep faces and burned-in captions inside the "
    "center safe area. Reframe archival 16:9; do not stretch. "
    "Bake brief only — this tool does not render video."
)

# (letter, label, heading prefixes in preference order)
SLOTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("A", "Cold open", ("cold open",)),
    ("B", "The fiction", ("act 1",)),
    ("C", "The reveal", ("act 3", "act 2")),
    ("D", "Aftermath and close", ("act 4", "cta")),
)

_STOP = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "were",
    "been",
    "they",
    "their",
    "what",
    "when",
    "your",
    "into",
    "over",
    "after",
    "before",
    "about",
    "would",
    "could",
    "there",
    "which",
    "while",
    "where",
    "shall",
    "these",
    "those",
    "being",
    "until",
    "under",
    "other",
    "only",
    "than",
    "then",
    "them",
    "because",
    "through",
    "without",
    "first",
    "later",
    "still",
    "every",
}


def _tokens(text: str) -> set[str]:
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z']{5,}", text)
        if word.lower() not in _STOP
    }


def _overlap(left: set[str], right: set[str]) -> int:
    return len(left & right)


def _label_phrase(heading: str) -> str | None:
    """Phrase that is meaningful only when the cue label names the section."""
    lowered = heading.lower()
    if lowered.startswith("cold open"):
        return "cold open"
    if lowered.startswith("channel intro"):
        return "channel intro"
    return None


def _pick_section(sections: list[VoSection], prefixes: tuple[str, ...]) -> VoSection | None:
    for prefix in prefixes:
        for section in sections:
            if section.heading.lower().startswith(prefix):
                return section
    return None


def _line_ref(section: VoSection | None) -> str:
    if section is None or section.first_spoken_line is None:
        return "VO line ref: none (section not in the VO-timing file)"
    end = section.hook_end_line or section.first_spoken_line
    if end <= section.first_spoken_line:
        return f"VO L{section.first_spoken_line} · {section.heading}"
    return f"VO L{section.first_spoken_line}–L{end} · {section.heading}"


def _cta_beat(sections: list[VoSection]) -> str:
    for section in sections:
        if section.heading.lower().startswith("cta"):
            quote = first_sentences(section.plain, n=1, limit=240)
            if quote:
                return f"{quote} Full episode: {LONG_FORM_URL}"
    return (
        f"End card only — {CHANNEL_NAME}. "
        f"Full episode: {LONG_FORM_URL}. Do not invent a spoken CTA."
    )


def _assign_cues(cuts: list[dict], cues: list) -> dict[str, object]:
    """Attach at most one CLIP-NOTES cue per cut when the label names the beat.

    Cue timecodes stay clip timecodes. The caller lists every unassigned cue
    in the shotlist appendix instead of turning it into an episode timestamp.
    """
    if not cues:
        return {}
    assigned: dict[str, object] = {}
    used_cues: set[int] = set()
    for cut in cuts:
        phrase = _label_phrase(cut["heading"])
        if not phrase:
            continue
        for qi, cue in enumerate(cues):
            if phrase in cue.label.lower():
                assigned[cut["letter"]] = cue
                used_cues.add(qi)
                break

    token_sets = {
        cut["letter"]: _tokens(f"{cut['heading']} {cut['hook']}") for cut in cuts
    }
    cue_tokens = [_tokens(cue.label) for cue in cues]
    cue_df: dict[str, int] = {}
    for toks in cue_tokens:
        for tok in toks:
            cue_df[tok] = cue_df.get(tok, 0) + 1
    # Topic words (the episode name, repeated on most cues) are not a beat match.
    noisy = {tok for tok, count in cue_df.items() if count >= 3}
    for letter, toks in token_sets.items():
        token_sets[letter] = toks - noisy

    pairs: list[tuple[int, int, str, int]] = []
    for cut in cuts:
        if cut["letter"] in assigned:
            continue
        for qi, toks in enumerate(cue_tokens):
            if qi in used_cues:
                continue
            score = _overlap(token_sets[cut["letter"]], toks - noisy)
            if score > 0:
                pairs.append((score, -qi, cut["letter"], qi))
    pairs.sort(reverse=True)
    for _score, _neg, letter, qi in pairs:
        if letter in assigned or qi in used_cues:
            continue
        assigned[letter] = cues[qi]
        used_cues.add(qi)
    return assigned


def _picture_line(cue) -> str:
    label = re.sub(r"\s+", " ", cue.label).strip()
    return (
        f"{cue.in_tc}–{cue.out_tc} · {cue.clip} — {label} "
        "(CLIP-NOTES clip timecode, not the episode timeline)"
    )


def build_shotlist(
    *,
    ep: int,
    title: str | None,
    sections: list[VoSection],
    cues: list,
) -> str:
    cta = _cta_beat(sections)
    cuts: list[dict] = []
    for letter, label, prefixes in SLOTS:
        section = _pick_section(sections, prefixes)
        hook = first_sentences(section.plain, n=2, limit=280) if section else ""
        cuts.append(
            {
                "letter": letter,
                "label": label,
                "heading": section.heading if section else "",
                "hook": hook,
                "line_ref": _line_ref(section),
            }
        )
    assigned = _assign_cues(cuts, cues)
    used_ids = {id(cue) for cue in assigned.values()}

    heading = f"# Shorts shotlist — Ep {ep:02d}"
    if title:
        heading += f" {title.strip()}"
    lines = [
        heading,
        "",
        f"Channel: {CHANNEL_NAME} ({CHANNEL_SHORT})",
        "",
        "Bake brief only. This tool does not render video, upload, or unlock Distro.",
        "distro_blocked: true",
        f"Long-form URL placeholder: {LONG_FORM_URL}",
        "",
    ]
    for cut in cuts:
        hook = cut["hook"] or "(No matching VO section in the input. Do not invent a hook.)"
        cue = assigned.get(cut["letter"])
        if cue is not None:
            picture = _picture_line(cue)
        elif cues:
            picture = "none matched in CLIP-NOTES. Use the VO line ref."
        else:
            picture = "no CLIP-NOTES supplied. Use the VO line ref."
        lines.extend(
            [
                f"## {cut['letter']} — {cut['label']}",
                "",
                f"- Hook: {hook}",
                f"- In/out: {cut['line_ref']}",
                f"- Picture: {picture}",
                f"- CTA beat: {cta}",
                f"- 9:16: {NINE_SIXTEEN}",
                "",
            ]
        )

    leftover = [cue for cue in cues if id(cue) not in used_ids]
    if leftover:
        lines.extend(["## Other CLIP-NOTES cues (not assigned)", ""])
        for cue in leftover:
            lines.append(f"- {_picture_line(cue)}")
        lines.append("")
    return "\n".join(lines)


def run_shorts_cutter(
    *,
    ep: int,
    vo_timing: Path | str,
    clip_notes: Path | str | None = None,
    title: str | None = None,
    out_dir: Path | str | None = None,
) -> dict:
    """Write shorts/epXX/SHORTS-SHOTLIST.md plus machine JSON."""
    vo_path = Path(vo_timing)
    clips_path = Path(clip_notes) if clip_notes else None
    episode_id = episode_id_for(ep)
    out = Path(out_dir) if out_dir else Path("shorts") / episode_id
    out.mkdir(parents=True, exist_ok=True)

    vo_text = vo_path.read_text(encoding="utf-8")
    sections = parse_sections(vo_text)
    cues = parse_duck_cues(clips_path) if clips_path else []
    clip_text = clips_path.read_text(encoding="utf-8") if clips_path else ""

    shotlist = build_shotlist(ep=ep, title=title, sections=sections, cues=cues)
    shot_path = out / "SHORTS-SHOTLIST.md"
    shot_path.write_text(shotlist, encoding="utf-8")

    sources = renumber_sources(
        extract_sources(vo_text, str(vo_path))
        + (extract_sources(clip_text, str(clips_path)) if clip_text and clips_path else [])
    )
    fences = merge_fences(
        extract_fences(vo_text, "vo"),
        extract_fences(clip_text, "clips") if clip_text else [],
    )
    asset_index = [
        {"role": "vo-timing", "path": str(vo_path)},
        {"role": "shorts-shotlist", "path": "SHORTS-SHOTLIST.md"},
        {"role": "machine", "path": "machine.json"},
    ]
    if clips_path:
        asset_index.insert(1, {"role": "clip-notes", "path": str(clips_path)})
        for cue in cues:
            asset_index.append(
                {
                    "role": "clip-cue",
                    "path": cue.clip,
                    "in": cue.in_tc,
                    "out": cue.out_tc,
                    "label": cue.label,
                }
            )

    block = machine_block(
        episode_id=episode_id,
        sources=sources,
        fences=fences,
        asset_index=asset_index,
        tool="shorts-cutter",
        channel=CHANNEL_NAME,
        channel_short=CHANNEL_SHORT,
        renders_video=False,
        uploads=False,
    )
    machine_path = out / "machine.json"
    block = write_machine(machine_path, block)
    print(f"wrote {shot_path}")
    print(f"wrote {machine_path}")
    print("distro_blocked: true")
    print("no render; agent/Cut uses this as a bake brief")
    return {
        "out_dir": out,
        "shotlist": shot_path,
        "machine_path": machine_path,
        "machine": block,
    }
