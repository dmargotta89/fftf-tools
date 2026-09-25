from pathlib import Path

from fftf_tools.drive_checklist import CHECK_ITEMS, build_checklist, write_drive_checklist


def test_checklist_items():
    text = build_checklist(3, "Watergate")
    assert "FFTF Ep03" in text
    assert "Watergate" in text
    for item in CHECK_ITEMS:
        assert f"- [ ] {item}" in text


def test_write_file(tmp_path: Path):
    out = tmp_path / "checklist.md"
    path = write_drive_checklist(3, "Watergate", out_file=out)
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert "verifier PASS" in body
    assert "Distro stamp" in body
