"""Spoken-body helpers and the cartoon/spine vocab fence.

The fence applies to narration that could be recorded. Fence rules, source
lists, and production notes are not spoken, so naming the locked words there
does not trip the gate.
"""

from __future__ import annotations

import re

LOCKED_WORDS = ("cartoon", "spine")

_SPOKEN_HEADER = re.compile(
    r"^##\s+(?:COLD OPEN|CHANNEL INTRO|ACT\s+\d|Full narration|Fiction|Pushback|Reveal|Aftermath)\b",
    re.I,
)
_HEADER = re.compile(r"^##\s+(\S.*)$")
_INSTRUCTION_WORDS = {
    "avoid",
    "and",
    "contain",
    "do",
    "dont",
    "don't",
    "forbidden",
    "must",
    "never",
    "no",
    "not",
    "or",
    "say",
    "the",
    "use",
    "word",
    "words",
}


def word_pattern(word: str) -> re.Pattern[str]:
    return re.compile(rf"\b{re.escape(word)}\b", re.I)


def find_word_hits(text: str, words: list[str] | tuple[str, ...]) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for word in words:
        pattern = word_pattern(word)
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            excerpt = text.splitlines()[line - 1].strip()
            hits.append({"word": match.group(0), "line": line, "excerpt": excerpt})
    return hits


def spoken_sections(text: str) -> list[tuple[str, str]]:
    """Return ``(heading, body)`` for narration sections, if any exist."""
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    buf: list[str] = []
    for line in lines:
        header = _HEADER.match(line)
        if header:
            if heading is not None:
                sections.append((heading, "\n".join(buf).strip()))
            title = header.group(1).strip()
            heading = title if _SPOKEN_HEADER.match(line) else None
            buf = []
            continue
        if heading is not None:
            buf.append(line)
    if heading is not None:
        sections.append((heading, "\n".join(buf).strip()))
    return [(title, body) for title, body in sections if title]


def has_spoken_headers(text: str) -> bool:
    return any(_SPOKEN_HEADER.match(line) for line in text.splitlines())


def extract_spoken(text: str) -> str:
    """Narration only. Headings, fences, sources, and preambles stay out."""
    if has_spoken_headers(text):
        bodies = [body for _, body in spoken_sections(text) if body]
        return "\n\n".join(bodies).strip()
    return "\n".join(line for _, line in iter_spoken_lines(text)).strip()


def iter_spoken_lines(text: str):
    """Yield ``(line_number, line)`` for narration. Fence and source sections stay out."""
    headers = has_spoken_headers(text)
    capturing = not headers
    for line_no, line in enumerate(text.splitlines(), 1):
        if _HEADER.match(line):
            capturing = bool(_SPOKEN_HEADER.match(line)) if headers else False
            continue
        if capturing:
            yield line_no, line


def spoken_hits(text: str, words: list[str] | tuple[str, ...] | None = None) -> list[dict[str, object]]:
    """Line hits inside the spoken body. Line numbers refer to ``text``."""
    words = list(words or LOCKED_WORDS)
    hits: list[dict[str, object]] = []
    for line_no, line in iter_spoken_lines(text):
        for word in words:
            for match in word_pattern(word).finditer(line):
                hits.append({"word": match.group(0), "line": line_no, "excerpt": line.strip()})
    return hits


def section_body(text: str, name: str) -> str:
    match = re.search(rf"^##\s+{re.escape(name)}\s*$", text, re.I | re.M)
    if not match:
        return ""
    rest = text[match.end() :]
    nxt = re.search(r"^##\s+", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    return body.strip()


def normalize_spoken(text: str) -> str:
    """Compare draft and narration after markers and markdown emphasis drop out."""
    cleaned = re.sub(r"\[(?:br|p|P)\]", " ", text)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"[*_`]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def locked_words_from_vocab(vocab: object) -> list[str]:
    """Always include cartoon and spine. Extra lock words come from ``vocab``."""
    found: list[str] = []

    def add(word: str) -> None:
        token = word.strip().lower()
        if len(token) < 3 or token in _INSTRUCTION_WORDS:
            return
        if token not in found:
            found.append(token)

    for word in LOCKED_WORDS:
        add(word)
    if isinstance(vocab, str):
        for token in re.findall(r"[A-Za-z']+", vocab):
            add(token)
    elif isinstance(vocab, list):
        for item in vocab:
            for token in re.findall(r"[A-Za-z']+", str(item)):
                add(token)
    return found


def contains_locked_word(text: str, words: list[str] | tuple[str, ...]) -> bool:
    return any(word_pattern(word).search(text) for word in words)
