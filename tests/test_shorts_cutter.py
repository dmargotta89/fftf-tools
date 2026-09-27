import json
from pathlib import Path

from click.testing import CliRunner

from fftf_tools.cli import main
from fftf_tools.schema import validate_machine
from fftf_tools.shorts_cutter import run_shorts_cutter


def test_shorts_cutter_with_clip_notes(vo_sample: Path, clip_notes: Path, tmp_path: Path):
    out = tmp_path / "shorts" / "ep03"
    result = run_shorts_cutter(
        ep=3,
        vo_timing=vo_sample,
        clip_notes=clip_notes,
        title="Watergate",
        out_dir=out,
    )
    text = (out / "SHORTS-SHOTLIST.md").read_text(encoding="utf-8")
    assert "From Fiction to Fact (FFTF)" in text
    assert "distro_blocked: true" in text
    assert "June 17, 1972." in text
    assert "Five men in suits" in text
    assert "United States v. Nixon" in text
    assert "What is true now?" in text
    assert "03:18" in text and "03:32" in text
    assert "CLIP-NOTES clip timecode" in text
    cold = text.split("## B —")[0]
    fiction = text.split("## B —")[1].split("## C —")[0]
    assert "Good evening" in cold
    assert "none matched in CLIP-NOTES" in fiction
    for letter in ("A", "B", "C", "D"):
        assert f"## {letter} —" in text
    assert text.count("- Hook:") == 4
    assert text.count("- In/out:") == 4
    assert text.count("- CTA beat:") == 4
    assert text.count("- 9:16:") == 4
    assert "VO L" in text
    assert "{{LONG_FORM_URL}}" in text
    assert "1080×1920" in text

    data = json.loads((out / "machine.json").read_text(encoding="utf-8"))
    assert data["episode_id"] == "ep03"
    assert data["distro_blocked"] is True
    assert data["channel"] == "From Fiction to Fact"
    assert data["tool"] == "shorts-cutter"
    assert data["renders_video"] is False
    assert data["uploads"] is False
    assert data["sources"]
    clip_text = clip_notes.read_text(encoding="utf-8")
    vo_text = vo_sample.read_text(encoding="utf-8")
    for source in data["sources"]:
        assert source["verified"] is False
        assert source["url"] == source["locator"]
        assert source["n"] >= 1
        assert source["locator"] in clip_text or source["locator"] in vo_text
    assert all(item["rule"] and item["status"] in {"held", "broken", "unknown"} for item in data["fences"])
    assert validate_machine(data) == []
    assert any(item["id"] == "no-distro" for item in data["fences"])
    roles = {item["role"] for item in data["asset_index"]}
    assert {"vo-timing", "clip-notes", "shorts-shotlist", "machine"} <= roles
    assert result["machine"]["distro_blocked"] is True


def test_shorts_without_clips_uses_line_refs(vo_sample: Path, tmp_path: Path):
    out = tmp_path / "bare"
    run_shorts_cutter(ep=3, vo_timing=vo_sample, out_dir=out)
    text = (out / "SHORTS-SHOTLIST.md").read_text(encoding="utf-8")
    assert "no CLIP-NOTES supplied" in text
    assert "03:18" not in text
    data = json.loads((out / "machine.json").read_text(encoding="utf-8"))
    assert data["distro_blocked"] is True
    assert data["sources"] == []


def test_shorts_cli(vo_sample: Path, clip_notes: Path, tmp_path: Path):
    runner = CliRunner()
    help_result = runner.invoke(main, ["shorts-cutter", "--help"])
    assert help_result.exit_code == 0
    assert "--publish" not in help_result.output
    assert "--render" not in help_result.output

    out = tmp_path / "cli-shorts"
    result = runner.invoke(
        main,
        [
            "shorts-cutter",
            "--ep",
            "3",
            "--title",
            "Watergate",
            "--vo",
            str(vo_sample),
            "--clips",
            str(clip_notes),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "distro_blocked: true" in result.output
    assert "no render" in result.output
    assert (out / "SHORTS-SHOTLIST.md").is_file()
