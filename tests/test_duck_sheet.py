import csv
from pathlib import Path

from fftf_tools.duck_sheet import parse_duck_cues, run_duck_sheet


def test_parse_clip_notes(clip_notes: Path):
    cues = parse_duck_cues(clip_notes)
    assert len(cues) >= 5
    hero = [c for c in cues if "03:18" in c.in_tc and "03:32" in c.out_tc]
    assert hero
    assert hero[0].duration_s == 14.0
    assert "resign" in hero[0].label.lower() or "HERO" in hero[0].label


def test_parse_cut_av_duck(duck_cues: Path):
    cues = parse_duck_cues(duck_cues)
    assert len(cues) >= 4
    assert any(c.in_tc == "01:12" for c in cues)


def test_write_outputs(clip_notes: Path, tmp_path: Path):
    prefix = tmp_path / "ep03-duck"
    csv_path, md_path = run_duck_sheet(clip_notes, out_prefix=prefix)
    assert csv_path.exists()
    assert md_path.exists()
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert set(rows[0].keys()) == {
        "clip",
        "in",
        "out",
        "duration_s",
        "label",
        "vo_pause_note",
    }
