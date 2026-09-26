"""fftf script-strip — draft, narration-only, VO-timing, and delta from a brief.

v1 writes a structured template with TODO markers, not a full documentary.
Spoken files never contain the locked words. Word counts are counted from the
files that were written. Distro stays blocked.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fftf_tools.schema import (
    CHANNEL_DISPLAY,
    ContractError,
    Fence,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    hold_tool_fences,
    find_sibling_machine,
    merge_fences,
    normalize_episode_id,
    one_line,
    read_machine,
    slugify,
    write_machine,
)
from fftf_tools.vocab import (
    LOCKED_WORDS,
    contains_locked_word,
    extract_spoken,
    locked_words_from_vocab,
    section_body,
    spoken_hits,
)
from fftf_tools.vo_check import spoken_stats

_SOURCE_LINE = re.compile(
    r"^\s*(\d+)\.\s+(https?://\S+|PLACEHOLDER)\s*(?:[—–-]\s*)?(.*)$",
    re.I,
)


def _load_locks(path: Path) -> dict:
    if not path.is_file():
        raise ContractError(f"locks file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"locks JSON is invalid: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("locks JSON must be an object")
    return data


def _episode_from_text(text: str) -> str | None:
    match = re.search(r"(?m)^Episode:\s*([A-Za-z0-9][A-Za-z0-9-]*)\s*$", text)
    if not match:
        return None
    return normalize_episode_id(match.group(1))


def _sources_from_brief(text: str) -> list[Source]:
    sources: list[Source] = []
    for line in section_body(text, "Sources").splitlines():
        match = _SOURCE_LINE.match(line.strip())
        if not match:
            continue
        label = match.group(3).strip() or "source"
        sources.append(Source(n=int(match.group(1)), url=match.group(2), label=label))
    return sources


def _safe_phrase(text: str, words: list[str], notes: list[str], label: str) -> str:
    cleaned = one_line(text)
    if contains_locked_word(cleaned, words):
        notes.append(f"{label} contained a locked spoken word and was not copied into narration.")
        return ""
    return cleaned


def _prose_sentences(body: str, words: list[str], dropped: list[str]) -> list[str]:
    kept: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        if re.search(r"\bTODO\b", line, re.I) or "PLACEHOLDER" in line.upper():
            continue
        line = re.sub(r"\[(?:br|p|P)\]", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if contains_locked_word(part, words):
                dropped.append(part)
                continue
            if part[-1] not in ".!?":
                part += "."
            kept.append(part)
    return kept


def _todo(label: str, topic: str, year_window: str, words: list[str]) -> str:
    window = year_window if not contains_locked_word(year_window, words) else "the year window"
    subject = topic if not contains_locked_word(topic, words) else "this story"
    sentence = f"TODO: write the {label} beat for {subject} in {window}."
    if contains_locked_word(sentence, words):
        return "TODO: write this beat from the brief after the vocab lock."
    return sentence


def _render_marked(sentences: list[str]) -> str:
    if not sentences:
        return ""
    chunks: list[str] = ["[P]"]
    for index, sentence in enumerate(sentences):
        pause = "[P]" if index == len(sentences) - 1 else "[p]"
        chunks.append(sentence)
        chunks.append(pause)
    return " ".join(chunks)


def _assert_clean(name: str, text: str, words: list[str]) -> None:
    hits = spoken_hits(text, words)
    raw = []
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text, re.I):
            raw.append(word)
    if hits or raw:
        raise ContractError(f"{name} would emit a locked spoken word; strip aborted")


def run_script_strip(
    brief_path: Path | str,
    locks_path: Path | str,
    out_dir: Path | str | None = None,
    episode_id: str | None = None,
) -> dict:
    brief_path = Path(brief_path)
    if not brief_path.is_file():
        raise ContractError(f"brief not found: {brief_path}")
    locks = _load_locks(Path(locks_path))
    words = locked_words_from_vocab(locks.get("vocab"))
    for required in LOCKED_WORDS:
        if required not in words:
            words.append(required)

    brief = brief_path.read_text(encoding="utf-8")
    sibling = find_sibling_machine(brief_path)
    machine = read_machine(sibling) if sibling else None
    episode_id = normalize_episode_id(
        episode_id
        or (machine.episode_id if machine else None)
        or _episode_from_text(brief)
        or slugify(brief_path.stem)
    )
    topic_match = re.search(r"(?m)^#\s+FFTF brief —\s+(.+)$", brief)
    topic = one_line(topic_match.group(1)) if topic_match else episode_id
    window_match = re.search(r"(?m)^Year window:\s*(.+)$", brief)
    year_window = one_line(window_match.group(1)) if window_match else "the year window"

    notes: list[str] = []
    dropped: list[str] = []
    spoken_topic = _safe_phrase(topic, words, notes, "Topic") or "this story"
    envelope = locks.get("envelope") if isinstance(locks.get("envelope"), dict) else {}
    cold_rules = locks.get("cold_open_rules")
    naming = locks.get("naming") if isinstance(locks.get("naming"), list) else [CHANNEL_DISPLAY]
    naming_text = ", ".join(str(item) for item in naming) if naming else CHANNEL_DISPLAY

    section_plan = [
        ("COLD OPEN", None, "cold open"),
        ("CHANNEL INTRO (locked — only topic changes)", None, "intro"),
        ("ACT 1 — THE FICTION", "Fiction", "fiction"),
        ("ACT 2 — THE PUSHBACK", "Pushback", "pushback"),
        ("ACT 3 — THE REVEAL", "Reveal", "reveal"),
        ("ACT 4 — THE AFTERMATH", "Aftermath", "aftermath"),
    ]
    coverage: list[tuple[str, bool, int, int]] = []
    sections: list[tuple[str, list[str]]] = []
    for heading, brief_name, label in section_plan:
        if heading.startswith("CHANNEL INTRO"):
            sentences = [
                "Welcome to From Fiction to Fact, where each episode brings you the truth behind a story that was once dismissed as fiction.",
                f"In this week's episode, we go from Fiction to Fact on {spoken_topic}.",
            ]
            coverage.append((heading, False, len(sentences), 0))
        elif heading.startswith("COLD OPEN"):
            sentences = [
                f"TODO: open {spoken_topic} in {year_window if not contains_locked_word(year_window, words) else 'the year window'} with one picture and one stake.",
                "TODO: hold the verdict until the documents are on the table.",
            ]
            sentences = [
                sentence
                if not contains_locked_word(sentence, words)
                else "TODO: open the episode with one picture and one stake."
                for sentence in sentences
            ]
            coverage.append((heading, False, len(sentences), 0))
        else:
            body = section_body(brief, brief_name or "")
            before = len(dropped)
            kept = _prose_sentences(body, words, dropped)
            had_prose = bool(kept) or (len(dropped) > before)
            if not kept:
                kept = [_todo(label, spoken_topic, year_window, words)]
            coverage.append((heading, had_prose, len(kept), len(dropped) - before))
            sentences = kept
        sections.append((heading, sentences))

    def render_body(marked: bool) -> str:
        blocks = []
        for heading, sentences in sections:
            body = _render_marked(sentences) if marked else " ".join(sentences)
            blocks.append(f"## {heading}\n\n{body}")
        return "\n\n".join(blocks) + "\n"

    narration_body = render_body(marked=False)
    vo_body = render_body(marked=True)
    word_count, duration_min, marker_counts = spoken_stats(extract_spoken(vo_body))
    plain_count, _, _ = spoken_stats(extract_spoken(narration_body))
    if plain_count != word_count:
        raise ContractError("narration and VO-timing word counts diverged; strip aborted")

    min_words = envelope.get("min_words") if isinstance(envelope, dict) else None
    max_words = envelope.get("max_words") if isinstance(envelope, dict) else None
    envelope_ok = True
    envelope_note = "No word envelope was set in locks."
    if isinstance(min_words, int) and word_count < min_words:
        envelope_ok = False
        envelope_note = (
            f"Spoken word count {word_count} is under the lock minimum {min_words}. "
            "v1 is a template; replace TODOs before treating the count as a full script."
        )
    elif isinstance(max_words, int) and word_count > max_words:
        envelope_ok = False
        envelope_note = f"Spoken word count {word_count} is over the lock maximum {max_words}."
    elif isinstance(min_words, int) or isinstance(max_words, int):
        envelope_note = f"Spoken word count {word_count} is inside the lock envelope."

    draft = "\n".join(
        [
            f"# {episode_id} draft",
            "",
            channel_line(),
            f"Episode: {episode_id}",
            "Status: v1 strip template. Replace TODOs before a VO bake.",
            "Do not Distro.",
            "",
            "## Production notes",
            "",
            "Not spoken. v1 script-strip writes a template. Word counts are counted from the spoken sections.",
            f"Display name: {CHANNEL_DISPLAY}. Naming lock: {naming_text}.",
            "See delta.md for the vocab log and any brief sentences that were dropped.",
            "",
            narration_body.rstrip(),
            "",
        ]
    )
    narration = "\n".join(
        [
            f"# {episode_id} narration-only",
            "",
            channel_line(),
            f"Episode: {episode_id}",
            "Do not Distro.",
            "",
            narration_body.rstrip(),
            "",
        ]
    )
    vo = "\n".join(
        [
            f"# {episode_id} VO-timing",
            "",
            channel_line(),
            f"Episode: {episode_id}",
            "Do not Distro.",
            "",
            "Markers: `[p]` is a sentence pause and `[P]` is a section pause. No mid-clause breath markers in this strip.",
            f"Spoken word count: {word_count}",
            f"Estimated duration minutes: {duration_min:.2f}",
            "",
            vo_body.rstrip(),
            "",
        ]
    )
    _assert_clean("draft.md", draft, words)
    _assert_clean("narration-only.md", narration, words)
    _assert_clean("vo-timing.md", vo, words)

    dropped_tokens = []
    for sentence in dropped:
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", sentence, re.I) and word not in dropped_tokens:
                dropped_tokens.append(word)
    if dropped:
        listed = "\n".join(f"- {sentence}" for sentence in dropped)
        vocab_log = (
            f"Dropped {len(dropped)} brief sentence(s) that contained a locked spoken word.\n"
            "Tokens: "
            + ", ".join(dropped_tokens or list(LOCKED_WORDS))
            + "\n\n"
            + listed
        )
    else:
        vocab_log = "No brief sentence was dropped. Spoken files do not contain the locked words."

    coverage_rows = [
        "| section | brief had prose | spoken sentences kept | dropped for vocab |",
        "|---|---|---|---|",
    ]
    for heading, had_prose, kept_n, dropped_n in coverage:
        coverage_rows.append(
            f"| {heading} | {'yes' if had_prose else 'no'} | {kept_n} | {dropped_n} |"
        )
    cold_note = one_line(str(cold_rules)) if cold_rules else "(none)"
    delta = "\n".join(
        [
            f"# Delta — {episode_id}",
            "",
            channel_line(),
            "Distro: blocked.",
            "",
            "## What this strip did",
            "",
            "v1 script-strip writes a structured template from the brief sections. It does not write a full documentary.",
            *([f"- {note}" for note in notes] if notes else ["- Topic and year window were safe to echo."]),
            "",
            "## Section coverage",
            "",
            *coverage_rows,
            "",
            "## Word count",
            "",
            f"Spoken words: {word_count}",
            f"Estimated minutes at 160 wpm plus pause markers: {duration_min:.2f}",
            f"Marker counts: [p]={marker_counts.get('[p]', 0)}, [P]={marker_counts.get('[P]', 0)}",
            envelope_note,
            "",
            "## Vocab lock",
            "",
            vocab_log,
            "",
            "## Cold open rules",
            "",
            "Copied here and not into the spoken cold open:",
            "",
            cold_note,
            "",
            "## TODOs left",
            "",
            f"Spoken TODO markers remain: {narration_body.upper().count('TODO')}",
            "",
            "## Files",
            "",
            "- draft.md",
            "- narration-only.md",
            "- vo-timing.md",
            f"- {episode_id}.machine.json",
            "",
        ]
    )

    sources = list(machine.sources) if machine and machine.sources else _sources_from_brief(brief)
    assets = list(machine.asset_index) if machine else []
    lock_fences = []
    if isinstance(locks.get("fences"), list):
        lock_fences = [Fence.from_dict(item) for item in locks["fences"]]
    fences = merge_fences(default_fences(), machine.fences if machine else [], lock_fences)
    hold_tool_fences(fences)
    for fence in fences:
        if fence.id in {"vocab-cartoon", "vocab-spine"}:
            fence.status = "held"

    out = Path(out_dir) if out_dir else Path(f"{episode_id}-script")
    out.mkdir(parents=True, exist_ok=True)
    (out / "draft.md").write_text(draft, encoding="utf-8")
    (out / "narration-only.md").write_text(narration, encoding="utf-8")
    (out / "vo-timing.md").write_text(vo, encoding="utf-8")
    (out / "delta.md").write_text(delta, encoding="utf-8")
    payload = contract_payload(
        episode_id,
        sources=sources,
        fences=fences,
        asset_index=assets,
        tool="script-strip",
        spoken_word_count=word_count,
        duration_min_estimate=round(duration_min, 4),
        outputs=[
            "draft.md",
            "narration-only.md",
            "vo-timing.md",
            "delta.md",
            f"{episode_id}.machine.json",
        ],
        envelope_ok=envelope_ok,
        vocab_dropped=len(dropped),
    )
    return write_machine(out / f"{episode_id}.machine.json", payload)
