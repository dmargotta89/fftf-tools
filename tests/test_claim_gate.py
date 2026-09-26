from pathlib import Path

from click.testing import CliRunner

from fftf_tools.claim_gate import gate_document
from fftf_tools.cli import main
from fftf_tools.schema import Fence, Source, default_fences


def _gate(text: str, sources=None, fences=None, narration: str | None = None) -> dict:
    return gate_document(
        text,
        sources=sources if sources is not None else [],
        fences=fences if fences is not None else default_fences(),
        narration_text=narration,
        episode_id="ep01-test",
        input_name="sample.md",
    )


def test_claim_gate_fails_on_cartoon_and_spine():
    cartoon = _gate("## COLD OPEN\n\nThis cartoon should not air.\n")
    assert cartoon["verdict"] == "FAIL"
    assert cartoon["distro_blocked"] is True
    assert any("cartoon" in edit.lower() for edit in cartoon["required_edits"])
    spine = _gate("## AFTERMATH\n\nThe spine of the tale is unverified.\n")
    assert spine["verdict"] == "FAIL"
    assert any("spine" in edit.lower() for edit in spine["required_edits"])


def test_claim_gate_fails_on_invented_quote_and_missing_url():
    quoted = _gate(
        '## Reveal\n\nHe told the room "we never touched the boat that night" and sat down.\n',
        sources=[Source(1, "https://catalog.archives.gov/id/123", "record")],
    )
    assert quoted["verdict"] == "FAIL"
    assert any("quotation" in edit.lower() for edit in quoted["required_edits"])

    cited = _gate(
        '## Reveal\n\nHe told the room "we never touched the boat that night" [1] and sat down.\n',
        sources=[Source(1, "https://catalog.archives.gov/id/123", "record")],
    )
    assert cited["verdict"] == "PASS"

    missing = _gate(
        "## Reveal\n\nIn 1975 the hearing record changed the public story.\n\n## Sources\n\n1. PLACEHOLDER — hearing\n",
        sources=[Source(1, "PLACEHOLDER", "hearing")],
    )
    assert missing["verdict"] == "FAIL"
    assert any("source url" in edit.lower() for edit in missing["required_edits"])


def test_claim_gate_fence_break_and_narration_mismatch():
    broken = _gate(
        "## Reveal\n\nThe submarine was never mentioned.\n",
        sources=[Source(1, "https://catalog.archives.gov/id/9", "record")],
        fences=default_fences()
        + [Fence("no-sub", "Spoken narration must not contain the word submarine.", "unknown")],
    )
    assert broken["verdict"] == "FAIL"
    assert any(item["id"] == "no-sub" and item["status"] == "broken" for item in broken["fence_results"])

    draft = "## COLD OPEN\n\nThe record is short.\n"
    narration = "## COLD OPEN\n\nThe record is long.\n"
    mismatched = _gate(
        draft,
        sources=[Source(1, "https://catalog.archives.gov/id/9", "record")],
        narration=narration,
    )
    assert mismatched["narration_match"] is False
    assert mismatched["verdict"] == "FAIL"


def test_claim_gate_cli_exit_code(tmp_path: Path):
    path = tmp_path / "narration.md"
    path.write_text("## COLD OPEN\n\nA cartoon line.\n", encoding="utf-8")
    result = CliRunner().invoke(main, ["claim-gate", str(path), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    machine = next((tmp_path / "out").rglob("*.machine.json"))
    assert '"distro_blocked": true' in machine.read_text(encoding="utf-8")
