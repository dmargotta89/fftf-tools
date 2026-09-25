"""Write Drive episode checklist markdown for FFTF."""

from __future__ import annotations

from pathlib import Path

CHECK_ITEMS = [
    "script",
    "verifier PASS",
    "VO bake",
    "remux private-review",
    "Shorts A-D",
    "thumb options",
    "Distro stamp",
]


def build_checklist(ep: int, title: str) -> str:
    lines = [
        f"# FFTF Ep{ep:02d} — {title} — Drive checklist",
        "",
        "Channel: From Fiction to Fact (FFTF)",
        "",
        "## Production gate",
        "",
    ]
    for item in CHECK_ITEMS:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("Do not Distro until all boxes are checked.")
    lines.append("")
    return "\n".join(lines)


def write_drive_checklist(
    ep: int,
    title: str,
    out_file: Path | str | None = None,
) -> Path:
    text = build_checklist(ep, title)
    if out_file is None:
        out_file = Path(f"fftf-ep{ep:02d}-drive-checklist.md")
    else:
        out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(text, encoding="utf-8")
    print(f"wrote {out_file}")
    return out_file
