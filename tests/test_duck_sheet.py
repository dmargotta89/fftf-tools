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


def test_sample_cue_counts_stay_stable(clip_notes: Path, duck_cues: Path):
    notes = parse_duck_cues(clip_notes)
    cues = parse_duck_cues(duck_cues)
    assert len(notes) == 14
    assert len(cues) == 9
    assert notes[0].source_path.endswith("nixon-resignation-address-1974-08-08.mp4")
    assert cues[0].label.startswith("“I shall resign")


def test_loose_list_shapes_and_skipped_remux(tmp_path: Path):
    notes = tmp_path / "CLIP-NOTES.md"
    notes.write_text(
        "\n".join(
            [
                "# Clips",
                "",
                "## 1. Test speech",
                "- Path: clips/test-speech.mp4",
                "- **01:00–01:14** (~14s) — duration outside bold",
                "- 01:20->01:34 (~14s) — arrow form",
                "- **00:01.5–00:09.5 (~8s)** — fractional seconds",
                "",
                "Longer pads: 03:00–03:20 (~20s), 04:00–04:10 (~10s).",
                "",
                "## Cut remux priority",
                "1. Hero **01:00–01:14** (~14s) — file #1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    cues = parse_duck_cues(notes)
    assert [(cue.in_tc, cue.out_tc, cue.duration_s, cue.label) for cue in cues] == [
        ("01:00", "01:14", 14.0, "duration outside bold"),
        ("01:20", "01:34", 14.0, "arrow form"),
        ("00:01.5", "00:09.5", 8.0, "fractional seconds"),
    ]
    assert all(cue.clip == "test-speech" for cue in cues)
    assert all(cue.source_path == "clips/test-speech.mp4" for cue in cues)


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
