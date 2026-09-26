import json
from pathlib import Path

from click.testing import CliRunner

from fftf_tools.cli import main


def test_agent_chain(tmp_path: Path, clip_notes: Path):
    runner = CliRunner()
    brief = tmp_path / "brief"
    claim1 = tmp_path / "claim1"
    script = tmp_path / "script"
    claim2 = tmp_path / "claim2"
    picture = tmp_path / "picture"
    thumb = tmp_path / "thumb"
    locks = tmp_path / "locks.json"
    locks.write_text(
        json.dumps(
            {
                "vocab": ["cartoon", "spine"],
                "naming": ["From Fiction to Fact"],
                "fences": [{"id": "no-invented-urls", "rule": "Do not invent primary-source URLs.", "status": "unknown"}],
                "cold_open_rules": "One picture and one stake.",
                "envelope": {"min_words": 1200, "max_words": 1800},
            }
        ),
        encoding="utf-8",
    )
    steps = [
        ["brief-pack", "--topic", "Glomar and Project Azorian", "--year-window", "1974", "--episode-id", "ep04-glomar-azorian", "-o", str(brief)],
        ["claim-gate", str(brief / "ep04-glomar-azorian-brief.md"), "-o", str(claim1)],
        ["script-strip", str(brief / "ep04-glomar-azorian-brief.md"), "--locks", str(locks), "-o", str(script)],
        ["claim-gate", str(script / "draft.md"), "--narration", str(script / "narration-only.md"), "-o", str(claim2)],
        ["picture-sync", str(script / "vo-timing.md"), str(clip_notes), "-o", str(picture)],
        ["thumb-pack", "--episode-id", "ep04-glomar-azorian", "--title-a", "The ship", "--title-b", "The cover", "--title-c", "The files", "-o", str(thumb)],
    ]
    for args in steps:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
        assert "distro_blocked: true" in result.output

    first = json.loads((claim1 / "reviews" / "ep04-glomar-azorian-brief.machine.json").read_text(encoding="utf-8"))
    second = json.loads((claim2 / "reviews" / "draft.machine.json").read_text(encoding="utf-8"))
    assert first["verdict"] == "PASS_WITH_EDITS"
    assert second["verdict"] == "PASS_WITH_EDITS"
    assert second["narration_match"] is True
    assert (picture / "DUCK-SCHEDULE.json").is_file()
    assert (thumb / "thumb-brief.md").is_file()
    machines = list(tmp_path.rglob("*.machine.json"))
    assert machines
    for path in machines:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["distro_blocked"] is True
