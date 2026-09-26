"""fftf brief-pack — skeleton brief, asset hunt, and machine contract.

The brief does not invent primary-source URLs. Agents fill research later.
Distro stays blocked.
"""

from __future__ import annotations

from pathlib import Path

from fftf_tools.schema import (
    CHANNEL_DISPLAY,
    ContractError,
    Fence,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    load_json_value,
    merge_fences,
    normalize_episode_id,
    one_line,
    parse_fences,
    slugify,
    write_machine,
)
from fftf_tools.vocab import LOCKED_WORDS, contains_locked_word, spoken_hits

PLACEHOLDER_URL = "PLACEHOLDER"

_SOURCE_LABELS = (
    "Primary document for this episode. Agent fills the URL.",
    "Contemporary account. Agent fills the URL.",
    "Official record or hearing. Agent fills the URL.",
)


def _safe_topic(topic: str) -> str:
    cleaned = one_line(topic)
    if not cleaned:
        raise ContractError("topic is required")
    if contains_locked_word(cleaned, LOCKED_WORDS):
        return "this episode"
    return cleaned


def _source_rows() -> list[Source]:
    return [
        Source(n=index, url=PLACEHOLDER_URL, label=label)
        for index, label in enumerate(_SOURCE_LABELS, 1)
    ]


def render_brief(
    episode_id: str,
    topic: str,
    year_window: str,
    fences: list[Fence],
) -> str:
    spoken_topic = _safe_topic(topic)
    fence_lines = "\n".join(f"- `{fence.id}`: {fence.rule}" for fence in fences) or "- (none)"
    source_lines = "\n".join(
        f"{source.n}. {PLACEHOLDER_URL} — {source.label}" for source in _source_rows()
    )
    return "\n".join(
        [
            f"# FFTF brief — {one_line(topic)}",
            "",
            channel_line(),
            f"Episode: {episode_id}",
            f"Year window: {one_line(year_window)}",
            "Status: skeleton. The agent fills research. Do not Distro.",
            "",
            "This file is a template. It does not assert researched facts and it does not invent primary-source URLs.",
            "",
            "## Fiction",
            "",
            f"TODO: name the public story {spoken_topic} will correct.",
            "TODO: say what people thought was true. Do not write a finished documentary paragraph in this skeleton.",
            "",
            "## Pushback",
            "",
            "TODO: name who first challenged that story, and which record they used.",
            "TODO: leave a source number once a real URL is in Sources.",
            "",
            "## Reveal",
            "",
            "TODO: name the document or testimony that changes the story.",
            "TODO: do not invent a quotation. Cite a source number after the URL is real.",
            "",
            "## Aftermath",
            "",
            "TODO: say what is true now, and what this episode will not claim.",
            "",
            "## Sources",
            "",
            "Do not invent primary-source URLs. Replace each PLACEHOLDER after research.",
            "",
            source_lines,
            "",
            "## Timeline",
            "",
            "- TODO: first dated beat. The agent fills the date and a source number.",
            "- TODO: pushback date and source number.",
            "- TODO: reveal date and source number.",
            "- TODO: aftermath date and source number.",
            "",
            "## Risk notes",
            "",
            "- Distro stays blocked. This pack does not publish, call YouTube or Spotify, or spend money.",
            "- No invented quotations. No invented primary-source URLs.",
            "- Spoken narration has a vocab lock. See Fences. Do not put those locked words in the spoken sections.",
            f"- Display name stays {CHANNEL_DISPLAY}. Short form is FFTF only.",
            "",
            "## Fences",
            "",
            fence_lines,
            "",
            "## Machine",
            "",
            f"See `{episode_id}.machine.json`. `distro_blocked` is true.",
            "",
        ]
    )


def render_asset_hunt(episode_id: str, topic: str, year_window: str) -> str:
    window = one_line(year_window)
    rows = [
        ("fiction", f"Public-domain or government stills or film tied to {window}", "PD or gov"),
        ("pushback", "Hearing, press record, or government catalog", "gov"),
        ("reveal", "Primary document scan from a national archive or agency reading room", "PD or gov"),
        ("aftermath", "Official photograph in the public domain", "PD"),
        ("cold_open", "Date-establishing public-domain image", "PD or gov"),
    ]
    table = [
        "| beat | look for | license | status |",
        "|---|---|---|---|",
    ]
    for beat, look, license in rows:
        table.append(f"| {beat} | {look} | {license} | TODO |")
    return "\n".join(
        [
            f"# Asset hunt — {episode_id}",
            "",
            channel_line(),
            f"Topic: {one_line(topic)}",
            f"Year window: {window}",
            "",
            "Search public-domain and government holdings only. Skip commercial network archives and Hollywood productions.",
            "",
            "## Targets",
            "",
            *table,
            "",
            "## Skip",
            "",
            "- Commercial network news packages",
            "- Hollywood dramatizations and other studio picture",
            "- Any clip that needs a paid license",
            "",
            "## Notes",
            "",
            "The agent fills paths into the machine `asset_index` after the hunt. Leave `sha256` empty until the file is in hand.",
            "Do not invent a source URL in this list.",
            "Distro stays blocked.",
            "",
        ]
    )


def run_brief_pack(
    topic: str,
    year_window: str,
    fences: str | None = None,
    out_dir: Path | str | None = None,
    episode_id: str | None = None,
) -> dict:
    if not one_line(topic):
        raise ContractError("topic is required")
    if not one_line(year_window):
        raise ContractError("year-window is required")
    episode_id = normalize_episode_id(episode_id or f"ep-{slugify(topic)}")
    user_fences = parse_fences(load_json_value(fences)) if fences else []
    fence_list = merge_fences(default_fences(), user_fences)
    out = Path(out_dir) if out_dir else Path(episode_id)
    out.mkdir(parents=True, exist_ok=True)

    brief_name = f"{episode_id}-brief.md"
    brief_text = render_brief(episode_id, topic, year_window, fence_list)
    hunt_text = render_asset_hunt(episode_id, topic, year_window)
    hits = spoken_hits(brief_text)
    if hits:
        raise ContractError(
            "brief-pack refused to write a spoken section that contains a locked word: "
            + ", ".join(str(hit["word"]) for hit in hits)
        )

    (out / brief_name).write_text(brief_text, encoding="utf-8")
    (out / "ASSET-HUNT.md").write_text(hunt_text, encoding="utf-8")
    payload = contract_payload(
        episode_id,
        sources=_source_rows(),
        fences=fence_list,
        asset_index=[],
        tool="brief-pack",
        outputs=[brief_name, "ASSET-HUNT.md", f"{episode_id}.machine.json"],
        topic=one_line(topic),
        year_window=one_line(year_window),
    )
    return write_machine(out / f"{episode_id}.machine.json", payload)
