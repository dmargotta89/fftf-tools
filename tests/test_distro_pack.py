import json
from pathlib import Path

from click.testing import CliRunner

from fftf_tools.cli import main
from fftf_tools.distro_pack import build_title, run_distro_pack
from fftf_tools.schema import validate_machine
from fftf_tools.vo_check import validate_vo_timing
from fftf_tools.vo_sections import estimated_duration_seconds, parse_sections


def test_distro_pack_sample(vo_sample: Path, tmp_path: Path):
    out = tmp_path / "distro" / "ep03"
    result = run_distro_pack(
        ep=3,
        title="Watergate",
        draft=vo_sample,
        vo_timing=vo_sample,
        thumb=Path("thumbs/ep03.png"),
        out_dir=out,
    )
    assert result["machine"]["distro_blocked"] is True
    for name in (
        "TITLE.txt",
        "DESCRIPTION.md",
        "TAGS.txt",
        "CHAPTERS.txt",
        "SHORTS-CAPTIONS.md",
        "machine.json",
    ):
        assert (out / name).is_file()

    title = (out / "TITLE.txt").read_text(encoding="utf-8").strip()
    assert title == "Watergate | From Fiction to Fact Ep 03"

    description = (out / "DESCRIPTION.md").read_text(encoding="utf-8")
    assert "From Fiction to Fact (FFTF)" in description
    assert "distro_blocked: true" in description
    assert "June 17, 1972." in description
    assert "PRIMARY SOURCE PLACEHOLDER" in description
    assert "catalog.archives.gov" not in description
    assert "spotify" not in description.lower()
    assert "watch?v=" not in description
    assert "{{LONG_FORM_URL}}" in description
    assert "thumbs/ep03.png" in description

    chapters = (out / "CHAPTERS.txt").read_text(encoding="utf-8").splitlines()
    assert chapters[0].startswith("0:00 ")
    assert "Cold open" in chapters[0]
    labels = " ".join(chapters)
    for needle in ("Channel intro", "Act 1", "Act 3", "CTA"):
        assert needle in labels
    assert all(not line.startswith("#") for line in chapters)

    captions = (out / "SHORTS-CAPTIONS.md").read_text(encoding="utf-8")
    for letter in ("A", "B", "C", "D"):
        assert f"## {letter} —" in captions
    assert "{{LONG_FORM_URL}}" in captions
    assert "From Fiction to Fact" in captions

    tags = (out / "TAGS.txt").read_text(encoding="utf-8")
    assert "From Fiction to Fact" in tags
    assert "FFTF" in tags
    assert "Watergate" in tags

    data = json.loads((out / "machine.json").read_text(encoding="utf-8"))
    assert data["episode_id"] == "ep03"
    assert data["distro_blocked"] is True
    assert data["channel"] == "From Fiction to Fact"
    assert data["channel_short"] == "FFTF"
    assert data["tool"] == "distro-pack"
    assert data["sources"] == []
    assert any(item["id"] == "no-distro" for item in data["fences"])
    assert any(item["id"] == "no-publish" for item in data["fences"])
    assert any(
        "will not treat a CIA plot to oust the President as fact" in item["text"]
        for item in data["fences"]
    )
    assert all(len(item["text"]) <= 300 for item in data["fences"])
    assert not any(item["text"].endswith("…") for item in data["fences"])
    roles = {item["role"] for item in data["asset_index"]}
    assert {"draft", "vo-timing", "thumb", "machine"} <= roles
    assert data["chapters_estimated"] is True
    assert data.get("publish") is not True
    assert data.get("uploads") is False

    voiced = validate_vo_timing(vo_sample)
    estimated = estimated_duration_seconds(parse_sections(vo_sample.read_text(encoding="utf-8")))
    assert voiced.duration_min is not None
    assert abs(estimated - voiced.duration_min * 60.0) < 2.0


def test_distro_pack_cli_and_help(vo_sample: Path, tmp_path: Path):
    runner = CliRunner()
    help_result = runner.invoke(main, ["distro-pack", "--help"])
    assert help_result.exit_code == 0
    assert "--publish" not in help_result.output
    assert "--unlock" not in help_result.output

    out = tmp_path / "pack"
    result = runner.invoke(
        main,
        [
            "distro-pack",
            "--ep",
            "3",
            "--title",
            "Watergate",
            "--draft",
            str(vo_sample),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "distro_blocked: true" in result.output
    data = json.loads((out / "machine.json").read_text(encoding="utf-8"))
    assert data["distro_blocked"] is True


def test_no_vo_headers_and_copied_locator_only(tmp_path: Path):
    draft = tmp_path / "narration.md"
    draft.write_text(
        "# Notes\n\n"
        "Plain narration without section headers.\n\n"
        "Locator already in the file: https://example.com/already-in-draft\n",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    run_distro_pack(ep=4, title="Case", draft=draft, out_dir=out)
    chapters = (out / "CHAPTERS.txt").read_text(encoding="utf-8")
    assert chapters.startswith("0:00 Case")
    description = (out / "DESCRIPTION.md").read_text(encoding="utf-8")
    assert "PRIMARY SOURCE PLACEHOLDER" in description
    assert "example.com" not in description
    assert "Do not invent a hook." in description
    data = json.loads((out / "machine.json").read_text(encoding="utf-8"))
    assert data["episode_id"] == "ep04"
    assert data["distro_blocked"] is True
    assert data["chapters_estimated"] is False
    assert len(data["sources"]) == 1
    assert data["sources"][0]["locator"] == "https://example.com/already-in-draft"
    assert data["sources"][0]["url"] == data["sources"][0]["locator"]
    assert data["sources"][0]["n"] == 1
    assert data["sources"][0]["verified"] is False
    assert all(item["rule"] and item["status"] in {"held", "broken", "unknown"} for item in data["fences"])
    assert any(item["id"] == "no-publish" and item["status"] == "held" for item in data["fences"])
    assert validate_machine(data) == []


def test_title_stays_within_youtube_limit():
    title = build_title(12, "W" * 180)
    assert len(title) <= 100
    assert title.endswith("| From Fiction to Fact Ep 12")
