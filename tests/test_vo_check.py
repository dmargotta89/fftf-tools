from pathlib import Path

from fftf_tools.vo_check import run_vo_check, validate_vo_timing


def test_vo_sample_passes_yt_window(vo_sample: Path):
    result = validate_vo_timing(vo_sample, min_min=8.0, max_min=12.0)
    assert result.word_count > 1000
    assert result.duration_min is not None
    assert result.ok, result.notes


def test_vo_check_exit_code(vo_sample: Path, capsys):
    code = run_vo_check(vo_sample, min_min=8.0, max_min=12.0)
    out = capsys.readouterr().out
    assert "vo-check:" in out
    assert code == 0


def test_vo_fails_too_short_window(vo_sample: Path):
    result = validate_vo_timing(vo_sample, min_min=30.0, max_min=40.0)
    assert not result.ok
    assert any("below --min-min" in n for n in result.notes)


def test_mid_clause_br_flagged(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text(
        "## COLD OPEN\n\n"
        "Hello there [br] world continues here. [p]\n\n"
        "## Cut notes\n\n1. something detailed enough\n",
        encoding="utf-8",
    )
    result = validate_vo_timing(bad, min_min=0.0, max_min=99.0)
    assert not result.ok
    assert any("mid-clause" in n for n in result.notes)
