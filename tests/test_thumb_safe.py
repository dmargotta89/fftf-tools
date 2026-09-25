from pathlib import Path

from PIL import Image

from fftf_tools.thumb_safe import draw_thumb_safe, safe_zone_box


def test_safe_zone_math():
    box = safe_zone_box(1280, 720, side=0.10, top=0.12, bottom=0.12)
    left, top, right, bottom = box
    assert left == 128
    assert top == round(720 * 0.12)
    assert right == round(1280 * 0.90) - 1
    assert bottom == round(720 * 0.88) - 1


def test_draw_overlay_yt_size(tmp_path: Path, capsys):
    src = tmp_path / "thumb.png"
    Image.new("RGB", (1280, 720), color=(20, 40, 80)).save(src)
    out = tmp_path / "overlay.png"
    info = draw_thumb_safe(src, overlay=out)
    assert info["is_1280x720"] is True
    assert out.exists()
    printed = capsys.readouterr().out
    assert "1280x720 OK" in printed
    assert "safe_zone_box:" in printed


def test_warn_non_yt(tmp_path: Path, capsys):
    src = tmp_path / "small.png"
    Image.new("RGB", (640, 360), color=(0, 0, 0)).save(src)
    draw_thumb_safe(src, overlay=tmp_path / "o.png")
    assert "WARN" in capsys.readouterr().out
