import json
import re
from pathlib import Path

from fftf_tools.script_strip import run_script_strip
from fftf_tools.vocab import extract_spoken
from fftf_tools.vo_check import spoken_stats, validate_vo_timing


def test_script_strip_counts_words_and_strips_vocab(tmp_path: Path):
    brief = tmp_path / "ep04-azorian-brief.md"
    brief.write_text(
        "\n".join(
            [
                "# FFTF brief — Azorian",
                "",
                "Channel: From Fiction to Fact (FFTF)",
                "Episode: ep04-azorian",
                "Year window: 1974",
                "",
                "## Fiction",
                "",
                "The public story was a cartoon with a spy spine.",
                "",
                "## Pushback",
                "",
                "TODO: name the challenge.",
                "",
                "## Reveal",
                "",
                "TODO: name the document.",
                "",
                "## Aftermath",
                "",
                "TODO: say what is true now.",
                "",
                "## Sources",
                "",
                "1. PLACEHOLDER — primary document",
                "",
            ]
        ),
        encoding="utf-8",
    )
    locks = tmp_path / "locks.json"
    locks.write_text(
        json.dumps(
            {
                "vocab": ["cartoon", "spine"],
                "naming": ["From Fiction to Fact"],
                "fences": [],
                "cold_open_rules": "Date, place, and stake. No verdict yet.",
                "envelope": {"min_words": 50, "max_words": 4000},
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "script"
    payload = run_script_strip(brief, locks, out_dir=out, episode_id="ep04-azorian")
    for name in ("draft.md", "narration-only.md", "vo-timing.md", "delta.md"):
        assert (out / name).is_file()
    narration = (out / "narration-only.md").read_text(encoding="utf-8")
    vo = (out / "vo-timing.md").read_text(encoding="utf-8")
    draft = (out / "draft.md").read_text(encoding="utf-8")
    for text in (narration, vo, draft):
        assert re.search(r"\bcartoon\b", text, re.I) is None
        assert re.search(r"\bspine\b", text, re.I) is None
    assert re.search(r"\bcartoon\b", (out / "delta.md").read_text(encoding="utf-8"), re.I)
    assert "[p]" in vo and "[P]" in vo
    assert "From Fiction to Fact" in narration
    counted = spoken_stats(extract_spoken(narration))[0]
    assert counted == spoken_stats(extract_spoken(vo))[0] == payload["spoken_word_count"]
    assert payload["spoken_word_count"] > 0
    assert payload["distro_blocked"] is True
    assert all(source["url"] == "PLACEHOLDER" for source in payload["sources"])
    result = validate_vo_timing(out / "vo-timing.md", min_min=0, max_min=99)
    assert not any(note.startswith("L") and "mid-clause" in note for note in result.notes)
