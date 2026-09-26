"""fftf thumb-pack — title-card options and a fixed checklist.

No external generative API. With no still, Pillow draws a high-contrast title
on a dark field. With a still, the still is contained and padded to
1280×720 and 1080×1350. Distro stays blocked.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from fftf_tools.schema import (
    CHANNEL_DISPLAY,
    ContractError,
    channel_line,
    contract_payload,
    default_fences,
    hold_tool_fences,
    normalize_episode_id,
    one_line,
    write_machine,
)
from fftf_tools.thumb_safe import safe_zone_box

YT_SIZE = (1280, 720)
IG_SIZE = (1080, 1350)
BG = (18, 18, 20)
INK = (245, 245, 245, 255)
ZONE = {"side": 0.10, "top": 0.12, "bottom": 0.12}
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


def _load_font(size: int) -> ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines = [words[0]]
    for word in words[1:]:
        trial = f"{lines[-1]} {word}"
        width, _height = _text_size(draw, trial, font)
        if width <= max_width:
            lines[-1] = trial
        else:
            lines.append(word)
    return lines


def contain_pad(src: Image.Image, size: tuple[int, int], bg: tuple[int, int, int] = BG) -> Image.Image:
    """Scale ``src`` to fit inside ``size`` and pad the leftover with ``bg``."""
    canvas = Image.new("RGB", size, bg)
    sw, sh = src.size
    tw, th = size
    scale = min(tw / sw, th / sh)
    resized = src.resize((max(1, int(sw * scale)), max(1, int(sh * scale))), Image.Resampling.LANCZOS)
    rw, rh = resized.size
    canvas.paste(resized, ((tw - rw) // 2, (th - rh) // 2))
    return canvas


def _block_fits(
    draw: ImageDraw.ImageDraw,
    lines: list[tuple[str, ImageFont.ImageFont]],
    max_width: int,
    max_height: int,
) -> bool:
    total = 0
    for text, font in lines:
        width, height = _text_size(draw, text, font)
        if width > max_width:
            return False
        total += height + 6
    return total <= max_height


def render_title_card(
    size: tuple[int, int],
    title: str,
    option_id: str,
    still: Path | None,
) -> tuple[Image.Image, bool]:
    if still is not None:
        base = contain_pad(Image.open(still).convert("RGB"), size, BG)
    else:
        base = Image.new("RGB", size, BG)
    image = base.convert("RGBA")
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = safe_zone_box(size[0], size[1], **ZONE)
    inset = 16
    box = (left + inset, top + inset, right - inset, bottom - inset)
    max_w = max(8, box[2] - box[0])
    max_h = max(8, box[3] - box[1])

    chosen: tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont, list[str], list[str]] | None = None
    for size_px in range(68, 15, -2):
        title_font = _load_font(size_px)
        channel_font = _load_font(max(15, size_px // 3))
        id_font = _load_font(max(15, size_px // 3))
        title_lines = _wrap(draw, title, title_font, max_w)
        channel_lines = _wrap(draw, CHANNEL_DISPLAY, channel_font, max_w)
        pieces = [(option_id, id_font), *[(line, channel_font) for line in channel_lines], *[(line, title_font) for line in title_lines]]
        if _block_fits(draw, pieces, max_w, max_h):
            chosen = (title_font, channel_font, id_font, title_lines, channel_lines)
            break
    if chosen is None:
        title_font = _load_font(16)
        channel_font = _load_font(14)
        id_font = _load_font(14)
        title_lines = _wrap(draw, title, title_font, max_w) or [title[:40]]
        channel_lines = _wrap(draw, CHANNEL_DISPLAY, channel_font, max_w) or [CHANNEL_DISPLAY]
    else:
        title_font, channel_font, id_font, title_lines, channel_lines = chosen

    # Bottom-align the title stack inside the inset. Option id sits at the top of the inset.
    stack: list[tuple[str, ImageFont.ImageFont]] = [
        *[(line, channel_font) for line in channel_lines],
        *[(line, title_font) for line in title_lines],
    ]
    stack_h = sum(_text_size(draw, text, font)[1] + 6 for text, font in stack)
    y = box[3] - stack_h
    if y < box[1] + 28:
        y = box[1] + 28
    bar_top = max(box[1], y - 10)
    draw.rectangle([box[0], bar_top, box[2], box[3]], fill=(0, 0, 0, 170))

    boxes: list[tuple[int, int, int, int]] = []
    id_w, id_h = _text_size(draw, option_id, id_font)
    id_xy = (box[0], box[1])
    draw.text(id_xy, option_id, font=id_font, fill=INK)
    boxes.append((id_xy[0], id_xy[1], id_xy[0] + id_w, id_xy[1] + id_h))

    cursor = y
    for text, font in stack:
        width, height = _text_size(draw, text, font)
        x = box[0]
        draw.text((x, cursor), text, font=font, fill=INK)
        boxes.append((x, cursor, x + width, cursor + height))
        cursor += height + 6

    safe = all(b[0] >= left and b[1] >= top and b[2] <= right and b[3] <= bottom for b in boxes)
    return image.convert("RGB"), safe


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _checklist(safe_zone_ok: bool, has_still: bool) -> list[str]:
    mark = lambda ok: "x" if ok else " "
    lines = [
        "## FIXED checklist",
        "",
        f"- [{mark(True)}] YouTube frame is 1280×720",
        f"- [{mark(True)}] Instagram frame is 1080×1350 with CONTAIN+pad",
        f"- [{mark(safe_zone_ok)}] Title and channel line sit inside the safe zone (side 10%, top 12%, bottom 12%)",
        "- [x] Options A, B, and C exist",
        "- [x] No external generative API",
        f"- [x] Channel display name is {CHANNEL_DISPLAY}",
        "- [x] distro_blocked is true",
        "- [ ] Human still review before any later desk step",
    ]
    if not has_still:
        lines.append("- [ ] Replace title-card placeholders with a rights-cleared still")
    return lines


def run_thumb_pack(
    title_a: str,
    title_b: str,
    title_c: str,
    still: Path | str | None = None,
    out_dir: Path | str | None = None,
    episode_id: str | None = None,
) -> dict:
    titles = [("A", one_line(title_a)), ("B", one_line(title_b)), ("C", one_line(title_c))]
    if any(not title for _option, title in titles):
        raise ContractError("title A, B, and C are required")
    still_path = Path(still) if still else None
    if still_path is not None and not still_path.is_file():
        raise ContractError(f"still not found: {still_path}")
    episode_id = normalize_episode_id(episode_id or "ep-thumb")
    out = Path(out_dir) if out_dir else Path(f"{episode_id}-thumb")
    out.mkdir(parents=True, exist_ok=True)

    options = []
    safe_flags: list[bool] = []
    for option_id, title in titles:
        yt_name = f"{episode_id}-thumb-{option_id}-yt-1280x720.png"
        ig_name = f"{episode_id}-thumb-{option_id}-ig-1080x1350.png"
        yt_image, yt_ok = render_title_card(YT_SIZE, title, option_id, still_path)
        ig_image, ig_ok = render_title_card(IG_SIZE, title, option_id, still_path)
        yt_image.save(out / yt_name, format="PNG")
        ig_image.save(out / ig_name, format="PNG")
        safe_flags.extend([yt_ok, ig_ok])
        options.append(
            {
                "id": option_id,
                "title_text": title,
                "yt_md5": _md5(out / yt_name),
                "ig_md5": _md5(out / ig_name),
                "yt_path": yt_name,
                "ig_path": ig_name,
                "placeholder": still_path is None,
            }
        )
    safe_zone_ok = all(safe_flags)
    fences = default_fences()
    hold_tool_fences(fences)
    mode = (
        "Still was contained and padded onto both frames. No generative API was called."
        if still_path is not None
        else "No still was provided. These PNGs are Pillow title cards on a dark field, not photographs. No generative API was called."
    )
    brief = "\n".join(
        [
            f"# Thumb brief — {episode_id}",
            "",
            channel_line(),
            "Distro: blocked (`distro_blocked` is true). This pack does not publish or spend money.",
            "",
            mode,
            "",
            *_checklist(safe_zone_ok, still_path is not None),
            "",
            "## Options",
            "",
            "| id | title | youtube md5 | instagram md5 | placeholder |",
            "|---|---|---|---|---|",
            *[
                f"| {opt['id']} | {opt['title_text'].replace('|', '/')} | {opt['yt_md5']} | {opt['ig_md5']} | {str(opt['placeholder']).lower()} |"
                for opt in options
            ],
            "",
            "Safe zone: side 10%, top 12%, bottom 12%, from the same box `thumb-safe` uses.",
            "YouTube lock: 1280×720. Instagram lock: 1080×1350 CONTAIN+pad.",
            "",
        ]
    )
    (out / "thumb-brief.md").write_text(brief, encoding="utf-8")
    payload = contract_payload(
        episode_id,
        sources=[],
        fences=fences,
        asset_index=[],
        tool="thumb-pack",
        options=options,
        safe_zone_ok=safe_zone_ok,
        outputs=["thumb-brief.md", f"{episode_id}.machine.json"]
        + [name for opt in options for name in (opt["yt_path"], opt["ig_path"])],
    )
    return write_machine(out / f"{episode_id}.machine.json", payload)
