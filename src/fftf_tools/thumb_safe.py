"""Draw YouTube thumbnail safe-zone overlay with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def safe_zone_box(
    width: int,
    height: int,
    side: float = 0.10,
    top: float = 0.12,
    bottom: float = 0.12,
) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) inclusive pixel box of safe zone."""
    left = int(round(width * side))
    right = int(round(width * (1.0 - side))) - 1
    top_px = int(round(height * top))
    bottom_px = int(round(height * (1.0 - bottom))) - 1
    return left, top_px, right, bottom_px


def draw_thumb_safe(
    zone_image: Path | str,
    overlay: Path | str | None = None,
    side: float = 0.10,
    top: float = 0.12,
    bottom: float = 0.12,
) -> dict:
    zone_image = Path(zone_image)
    img = Image.open(zone_image).convert("RGBA")
    width, height = img.size
    box = safe_zone_box(width, height, side=side, top=top, bottom=bottom)

    overlay_img = img.copy()
    draw = ImageDraw.Draw(overlay_img)
    # outer dim: draw translucent red outside safe zone via rectangles
    dim = (255, 0, 0, 80)
    left, top_px, right, bottom_px = box
    # top band
    draw.rectangle([0, 0, width - 1, top_px - 1], fill=dim)
    # bottom band
    draw.rectangle([0, bottom_px + 1, width - 1, height - 1], fill=dim)
    # left band
    draw.rectangle([0, top_px, left - 1, bottom_px], fill=dim)
    # right band
    draw.rectangle([right + 1, top_px, width - 1, bottom_px], fill=dim)
    # safe rect outline
    draw.rectangle([left, top_px, right, bottom_px], outline=(0, 255, 0, 255), width=3)

    if overlay is None:
        overlay = zone_image.with_name(zone_image.stem + "-safe-overlay.png")
    else:
        overlay = Path(overlay)
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay_img.save(overlay, format="PNG")

    is_yt = width == 1280 and height == 720
    if is_yt:
        print(f"size: {width}x{height} (1280x720 OK)")
    else:
        print(f"WARN: size {width}x{height} is not 1280x720")
    print(f"safe_zone_box: left={left} top={top_px} right={right} bottom={bottom_px}")
    print(f"wrote {overlay}")

    return {
        "width": width,
        "height": height,
        "is_1280x720": is_yt,
        "box": box,
        "overlay": overlay,
    }
