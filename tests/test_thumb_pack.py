import hashlib
from pathlib import Path

from PIL import Image

from fftf_tools.thumb_pack import YT_SIZE, IG_SIZE, BG, run_thumb_pack
from fftf_tools.thumb_safe import safe_zone_box


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _ink_inside_safe_zone(path: Path, size: tuple[int, int]) -> None:
    image = Image.open(path).convert("RGB")
    assert image.size == size
    left, top, right, bottom = safe_zone_box(size[0], size[1], side=0.10, top=0.12, bottom=0.12)
    inside = 0
    outside = 0
    for y in range(0, size[1], 2):
        for x in range(0, size[0], 2):
            red, green, blue = image.getpixel((x, y))
            if red > 220 and green > 220 and blue > 220:
                if left <= x <= right and top <= y <= bottom:
                    inside += 1
                else:
                    outside += 1
    assert inside > 10
    assert outside == 0


def test_thumb_pack_placeholders(tmp_path: Path):
    payload = run_thumb_pack(
        "The files",
        "The cover story",
        "What remains",
        out_dir=tmp_path,
        episode_id="ep04-azorian",
    )
    assert payload["distro_blocked"] is True
    assert payload["safe_zone_ok"] is True
    assert [opt["id"] for opt in payload["options"]] == ["A", "B", "C"]
    brief = (tmp_path / "thumb-brief.md").read_text(encoding="utf-8")
    assert "## FIXED checklist" in brief
    assert "From Fiction to Fact" in brief
    assert "No external generative API" in brief
    for opt in payload["options"]:
        yt = tmp_path / opt["yt_path"]
        ig = tmp_path / opt["ig_path"]
        assert _md5(yt) == opt["yt_md5"]
        assert _md5(ig) == opt["ig_md5"]
        assert opt["placeholder"] is True
        _ink_inside_safe_zone(yt, YT_SIZE)
        _ink_inside_safe_zone(ig, IG_SIZE)


def test_thumb_pack_contain_pad(tmp_path: Path):
    still = tmp_path / "still.png"
    Image.new("RGB", (100, 100), color=(180, 20, 20)).save(still)
    out = tmp_path / "pack"
    payload = run_thumb_pack(
        "Option A",
        "Option B",
        "Option C",
        still=still,
        out_dir=out,
        episode_id="ep04-azorian",
    )
    assert payload["safe_zone_ok"] is True
    assert payload["options"][0]["placeholder"] is False
    yt = Image.open(out / payload["options"][0]["yt_path"]).convert("RGB")
    assert yt.size == YT_SIZE
    assert yt.getpixel((0, 0)) == BG
    ig = Image.open(out / payload["options"][0]["ig_path"]).convert("RGB")
    assert ig.size == IG_SIZE
    assert ig.getpixel((0, 0)) == BG
