"""fftf claim-gate — verifier report for a brief, outline, or narration.

Hard fails: invented-quote heuristic, claimed facts with no real source URL,
fence breaks, the cartoon/spine vocab fence, and a draft/narration mismatch.
Distro stays blocked. This command does not publish.
"""

from __future__ import annotations

import re
from pathlib import Path

from fftf_tools.schema import (
    ContractError,
    Fence,
    Source,
    channel_line,
    contract_payload,
    default_fences,
    find_sibling_machine,
    TOOL_FENCE_IDS,
    load_json_value,
    merge_fences,
    normalize_episode_id,
    parse_fences,
    parse_sources,
    read_machine,
    slugify,
    write_machine,
)
from fftf_tools.vocab import (
    LOCKED_WORDS,
    extract_spoken,
    iter_spoken_lines,
    normalize_spoken,
    section_body,
    spoken_hits,
)
from fftf_tools.vo_check import spoken_stats

_QUOTE = re.compile(r"[\"“]([^\"”]{8,}?)[\"”]")
_CITE = re.compile(
    r"https?://|\[\d+\]|\(\s*source\b|\bsource\s*[:#]|\bsources?\s+\d+",
    re.I,
)
_YEAR = re.compile(r"\b(?:1[89]\d{2}|20\d{2})\b")
_FORBID = re.compile(
    r"(?:must not|do not|don't|never|avoid)\s+"
    r"(?:contain(?:ing)?|include|say(?:ing)?|use|claim(?:ing)?|state|write|speak(?:ing)?)?\s*"
    r"(?:the\s+words?\s+)?"
    r"[\"“']?([A-Za-z][^\"”']*?)[\"”']?\s*\.?$",
    re.I,
)
_SOURCE_LINE = re.compile(
    r"^\s*(\d+)\.\s+(https?://\S+|PLACEHOLDER)\s*(?:[—–-]\s*)?(.*)$",
    re.I,
)


def url_is_real(url: str) -> bool:
    token = url.strip()
    if not token:
        return False
    upper = token.upper()
    if "PLACEHOLDER" in upper or "TODO" in upper or upper in {"TBD", "N/A", "NONE"}:
        return False
    return bool(re.match(r"https?://\S+$", token))


def _episode_from_text(text: str) -> str | None:
    match = re.search(r"(?m)^Episode:\s*([A-Za-z0-9][A-Za-z0-9-]*)\s*$", text)
    if not match:
        return None
    return normalize_episode_id(match.group(1))


def parse_sources_markdown(text: str) -> list[Source]:
    sources: list[Source] = []
    for line in section_body(text, "Sources").splitlines():
        match = _SOURCE_LINE.match(line.strip())
        if not match:
            continue
        label = match.group(3).strip() or match.group(2)
        sources.append(Source(n=int(match.group(1)), url=match.group(2), label=label))
    return sources


def _forbid_literal(fence: Fence) -> str | None:
    if fence.pattern:
        return fence.pattern.strip()
    quoted = re.findall(r"[\"“]([^\"”]{2,80})[\"”]", fence.rule)
    if quoted:
        return quoted[0].strip()
    match = _FORBID.search(fence.rule.strip())
    if not match:
        return None
    literal = match.group(1).strip(" .")
    return literal or None


def _literal_in_text(literal: str, spoken: str) -> bool:
    if len(literal.split()) == 1:
        return bool(re.search(rf"\b{re.escape(literal)}\b", spoken, re.I))
    return literal.lower() in spoken.lower()


def evaluate_fence(fence: Fence, spoken: str) -> tuple[str, str]:
    if fence.id in TOOL_FENCE_IDS:
        return "held", "this tool enforces the fence and does not scan narration for it"
    literal = _forbid_literal(fence)
    if literal and len(literal.split()) <= 4:
        if _literal_in_text(literal, spoken):
            return "broken", f"spoken text matches {literal!r}"
        return "held", f"token check: spoken text does not contain {literal!r}"
    if literal and _literal_in_text(literal, spoken):
        return "broken", f"spoken text contains {literal!r}"
    if fence.status == "broken":
        return "broken", "marked broken in the fence list"
    if fence.status == "held" and not literal:
        return "held", "marked held; no shorter pattern to re-check"
    return "unknown", "no short machine-checkable pattern; left unknown"


def invented_quotes(text: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for line_no, line in iter_spoken_lines(text):
        if "TODO" in line.upper():
            continue
        for match in _QUOTE.finditer(line):
            quote = match.group(1).strip()
            if len(quote.split()) < 4:
                continue
            window = line[max(0, match.start() - 40) : match.end() + 80]
            if _CITE.search(window):
                continue
            found.append({"quote": quote, "line": line_no})
    return found


def claimed_fact_lines(text: str) -> list[str]:
    chunks = [extract_spoken(text)]
    timeline = section_body(text, "Timeline")
    if timeline:
        chunks.append(timeline)
    claims: list[str] = []
    for chunk in chunks:
        for raw in chunk.splitlines():
            line = raw.strip()
            if not line or line.startswith("|") or line.startswith("#"):
                continue
            if "TODO" in line.upper() or line.upper().startswith("PLACEHOLDER"):
                continue
            if _YEAR.search(line) or _QUOTE.search(line):
                claims.append(line)
    return claims


def gate_document(
    text: str,
    *,
    sources: list[Source],
    fences: list[Fence],
    narration_text: str | None = None,
    episode_id: str,
    input_name: str,
) -> dict:
    spoken = extract_spoken(text)
    word_count, _duration, _markers = spoken_stats(spoken)
    hard: list[str] = []
    soft: list[str] = []
    fence_results: list[dict[str, str]] = []

    vocab_words = list(LOCKED_WORDS)
    documents = [("input", text)]
    if narration_text is not None:
        documents.append(("narration", narration_text))

    for label, doc in documents:
        for hit in spoken_hits(doc, vocab_words):
            hard.append(
                f"Remove the word {hit['word']!r} from the {label} spoken body "
                f"(line {hit['line']}: {hit['excerpt']})."
            )

    for label, doc in documents:
        for item in invented_quotes(doc):
            hard.append(
                f"Source or delete this unsourced quotation in {label} "
                f"(line {item['line']}): {item['quote']}"
            )

    claims = claimed_fact_lines(text)
    if narration_text is not None:
        claims.extend(claimed_fact_lines(narration_text))
    real_urls = [source for source in sources if url_is_real(source.url)]
    placeholders = [source for source in sources if not url_is_real(source.url)]
    if claims and not real_urls:
        hard.append(
            "Claimed facts have no source URL. Replace PLACEHOLDER entries with real URLs. "
            "This tool will not invent one."
        )
    elif not sources:
        soft.append("No sources are listed yet.")
    if placeholders:
        soft.append(
            f"{len(placeholders)} source URL(s) are still placeholders. "
            "Replace them when research is in. Do not invent a URL."
        )

    spoken_for_fences = spoken
    if narration_text is not None:
        spoken_for_fences = spoken + "\n" + extract_spoken(narration_text)
    evaluated: list[Fence] = []
    for fence in fences:
        status, detail = evaluate_fence(fence, spoken_for_fences)
        fence_results.append(
            {"id": fence.id, "rule": fence.rule, "status": status, "detail": detail}
        )
        evaluated.append(Fence(id=fence.id, rule=fence.rule, status=status, pattern=fence.pattern))
        if status == "broken":
            hard.append(f"Fence `{fence.id}` is broken. {detail}")
        elif status == "unknown":
            soft.append(f"Fence `{fence.id}` is unknown. {detail}")

    narration_match: bool | None = None
    if narration_text is not None:
        narration_match = normalize_spoken(extract_spoken(text)) == normalize_spoken(
            extract_spoken(narration_text)
        )
        if not narration_match:
            hard.append("Make the draft spoken text match narration-only after markers are stripped.")

    if "TODO" in spoken.upper() or (
        narration_text is not None and "TODO" in extract_spoken(narration_text).upper()
    ):
        soft.append("Spoken body still contains TODO markers. Replace them before a VO bake.")

    if hard:
        verdict = "FAIL"
    elif soft:
        verdict = "PASS_WITH_EDITS"
    else:
        verdict = "PASS"

    return contract_payload(
        episode_id,
        sources=sources,
        fences=evaluated,
        asset_index=[],
        tool="claim-gate",
        verdict=verdict,
        fence_results=fence_results,
        required_edits=hard,
        soft_fails=soft,
        spoken_word_count=word_count,
        narration_match=narration_match,
        input_name=input_name,
    )


def render_verifier(payload: dict, input_path: Path) -> str:
    match = payload.get("narration_match")
    match_text = "n/a" if match is None else ("yes" if match else "no")
    fence_rows = [
        "| id | status | detail |",
        "|---|---|---|",
    ]
    for fence in payload.get("fence_results", []):
        detail = str(fence.get("detail", "")).replace("|", "\\|")
        fence_rows.append(f"| {fence.get('id', '')} | {fence.get('status', '')} | {detail} |")
    edits = payload.get("required_edits") or ["(none)"]
    soft = payload.get("soft_fails") or ["(none)"]
    source_lines = []
    for source in payload.get("sources", []):
        source_lines.append(f"- {source.get('n')}. {source.get('url')} — {source.get('label')}")
    if not source_lines:
        source_lines.append("- (none)")
    return "\n".join(
        [
            f"# Verifier — {payload['episode_id']}",
            "",
            channel_line(),
            f"Input: {input_path.name}",
            f"Verdict: **{payload['verdict']}**",
            "Distro: blocked (`distro_blocked` is true). This report does not publish, call YouTube or Spotify, or spend money.",
            "",
            f"Spoken word count: {payload.get('spoken_word_count', 0)}",
            f"Narration match: {match_text}",
            "",
            "## Fence results",
            "",
            *fence_rows,
            "",
            "## Required edits",
            "",
            *[f"- {item}" for item in edits],
            "",
            "## Soft fails",
            "",
            *[f"- {item}" for item in soft],
            "",
            "## Sources",
            "",
            *source_lines,
            "",
            "## Heuristics",
            "",
            "- Vocab fence: spoken lines only, case-insensitive word boundaries, for cartoon and spine.",
            "- Invented quote: a double-quoted span of 4 or more words with no URL, `[n]`, or source marker on that line. TODO lines are skipped.",
            "- Missing source URL: a spoken or timeline line with a year or a quotation, and no real http(s) URL in the source list. PLACEHOLDER is not a URL. This tool does not invent one.",
            "- Fence check: a short literal taken from the rule. Longer rules stay unknown unless the phrase is actually present.",
            "",
        ]
    )


def _resolve_context(path: Path, sources_arg: str | None, fences_arg: str | None) -> tuple[list[Source], list[Fence], list, str | None]:
    text = path.read_text(encoding="utf-8")
    sibling = find_sibling_machine(path)
    machine_sources: list[Source] = []
    machine_fences: list[Fence] = []
    machine_assets = []
    machine_episode = None
    if sibling is not None and sibling.resolve() != path.resolve():
        machine = read_machine(sibling)
        machine_sources = machine.sources
        machine_fences = machine.fences
        machine_assets = machine.asset_index
        machine_episode = machine.episode_id
    sources = parse_sources(load_json_value(sources_arg)) if sources_arg else machine_sources
    if not sources:
        sources = parse_sources_markdown(text)
    cli_fences = parse_fences(load_json_value(fences_arg)) if fences_arg else []
    fences = merge_fences(default_fences(), machine_fences, cli_fences)
    episode = machine_episode or _episode_from_text(text)
    return sources, fences, machine_assets, episode


def run_claim_gate(
    path: Path | str,
    *,
    sources: str | None = None,
    fences: str | None = None,
    narration: Path | str | None = None,
    out_dir: Path | str | None = None,
    episode_id: str | None = None,
) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ContractError(f"input not found: {path}")
    text = path.read_text(encoding="utf-8")
    resolved_sources, resolved_fences, assets, found_episode = _resolve_context(path, sources, fences)
    narration_text = None
    if narration is not None:
        narration_path = Path(narration)
        if not narration_path.is_file():
            raise ContractError(f"narration not found: {narration_path}")
        narration_text = narration_path.read_text(encoding="utf-8")
    episode_id = normalize_episode_id(
        episode_id or found_episode or slugify(path.stem)
    )
    payload = gate_document(
        text,
        sources=resolved_sources,
        fences=resolved_fences,
        narration_text=narration_text,
        episode_id=episode_id,
        input_name=path.name,
    )
    payload["asset_index"] = [asset.to_dict() for asset in assets]
    out = Path(out_dir) if out_dir else Path(f"{episode_id}-claim-gate")
    reviews = out / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    verifier_name = f"{path.stem}-verifier.md"
    machine_name = f"{path.stem}.machine.json"
    report = render_verifier(payload, path)
    (reviews / verifier_name).write_text(report, encoding="utf-8")
    payload["outputs"] = [f"reviews/{verifier_name}", f"reviews/{machine_name}"]
    return write_machine(reviews / machine_name, payload)
