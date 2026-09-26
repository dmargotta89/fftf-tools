import json
from pathlib import Path

from fftf_tools.duck_sheet import parse_duck_cues
from fftf_tools.picture_sync import run_picture_sync


def test_duck_schedule_reuses_parser(tmp_path: Path, vo_sample: Path, clip_notes: Path):
    payload = run_picture_sync(
        vo_sample,
        clip_notes,
        out_dir=tmp_path,
        episode_id="ep03-watergate",
    )
    schedule = json.loads((tmp_path / "DUCK-SCHEDULE.json").read_text(encoding="utf-8"))
    cues = parse_duck_cues(clip_notes)
    assert schedule["distro_blocked"] is True
    assert len(schedule["ducks"]) == len(cues) == len(payload["ducks"])
    hero = [duck for duck in schedule["ducks"] if duck["in"] == "03:18" and duck["out"] == "03:32"]
    assert hero
    assert hero[0]["duration_s"] == 14.0
    assert (tmp_path / "SHOT-MAP.md").is_file()
    assert (tmp_path / "PICTURE-SYNC-CHECK.md").is_file()
    assert payload["distro_blocked"] is True
    notes = clip_notes.read_text(encoding="utf-8")
    assert payload["sources"]
    for source in payload["sources"]:
        assert source["url"] in notes
    assert any(asset["license"] == "PD" for asset in payload["asset_index"])
    assert cues[0].source_path.endswith(".mp4")


def test_clean_duck_window(tmp_path: Path):
    notes = tmp_path / "CLIP-NOTES.md"
    notes.write_text(
        "\n".join(
            [
                "# Clips",
                "",
                "## 1. Test speech",
                "",
                "| Field | Value |",
                "|---|---|",
                "| **path** | `clips/test-speech.mp4` |",
                "| **license** | **PD** |",
                "",
                "| In→Out | Len | Line / beat |",
                "|---|---|---|",
                "| **01:00–01:14** | **~14s** | Hero line |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    vo = tmp_path / "vo-timing.md"
    vo.write_text(
        "\n".join(
            [
                "# vo",
                "Episode: ep09-clean",
                "",
                "## COLD OPEN",
                "",
                "One sentence here. [P]",
                "",
                "## ACT 1 — THE FICTION",
                "",
                "Another sentence here. [p]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    payload = run_picture_sync(vo, notes, out_dir=tmp_path / "out")
    assert payload["ducks"][0]["duration_s"] == 14.0
    assert payload["ducks"][0]["clip"] == "test-speech"
    gates = {gate["id"]: gate["status"] for gate in payload["qc_gates"]}
    assert gates["ducks-parsed"] == "pass"
    assert gates["duck-duration-window"] == "pass"
    assert gates["distro-blocked"] == "pass"
    assert payload["distro_blocked"] is True
