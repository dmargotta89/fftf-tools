# fftf-tools

Local production helpers for **From Fiction to Fact** (FFTF short form only).

These commands stay on the production desk. They do not publish, stamp Distro, or call external APIs.

## Install

Requires Python 3.10+. From a fresh clone:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Runtime dependencies are `click` and `pillow`. The `dev` extra adds `pytest`.

Confirm the entry point:

```bash
fftf --help
```

## CLI

Entry point: `fftf`

### 1. `vo-check` — validate VO-timing markdown

Checks strip/format consistency, flags mid-clause `[br]` chops, requires density/notes section content when those headers exist, estimates duration from spoken words + pause markers, and compares to `--min-min` / `--max-min` (defaults **8** / **12** for YT). Exit **0 PASS** / **1 FAIL**.

```bash
fftf vo-check samples/ep03-watergate-v1.1-vo-timing-v3.md
fftf vo-check path/to/vo-timing.md --min-min 8 --max-min 12
```

### 2. `duck-sheet` — CLIP-NOTES / duck-cue sheets

Parses `CLIP-NOTES.md` or `CUT-AV-DUCK-CUES` style markdown and writes `OUT_PREFIX.csv` + `OUT_PREFIX.md` with columns: `clip`, `in`, `out`, `duration_s`, `label`, `vo_pause_note`.

```bash
fftf duck-sheet samples/CLIP-NOTES.md -o /tmp/ep03-duck
fftf duck-sheet samples/CUT-AV-DUCK-CUES-2026-09-24.md --vo samples/ep03-watergate-v1.1-vo-timing-v3.md -o /tmp/ep03-cues
```

### 3. `drive-checklist` — Drive episode checklist

Writes an unchecked markdown checklist: script, verifier PASS, VO bake, remux private-review, Shorts A-D, thumb options, Distro stamp.

```bash
fftf drive-checklist --ep 3 --title "Watergate" -o /tmp/ep03-drive-checklist.md
```

### 4. `thumb-safe` — thumbnail safe-zone overlay

Loads an image with Pillow, draws the safe-zone rectangle, writes an overlay PNG, prints whether the image is **1280×720** (warns if not) and the safe-zone box coordinates.

```bash
fftf thumb-safe /path/to/thumb.png -o /tmp/thumb-safe.png --side 0.10 --top 0.12 --bottom 0.12
```

### 5. `distro-pack` — local Studio paste pack

Reads a stamped draft or narration-only file, plus optional VO-timing and a thumbnail path. Writes `distro/epXX/` (or `-o`):

- `TITLE.txt`
- `DESCRIPTION.md` — cold-open hook quoted from the draft, source placeholders, CTA, FFTF naming
- `TAGS.txt`
- `CHAPTERS.txt` — from VO-timing section headers when those headers exist (times are markup estimates, not a bake timeline)
- `SHORTS-CAPTIONS.md` — captions A–D with a long-form URL placeholder
- `machine.json` — always `"distro_blocked": true`

Does not upload. A human still pastes into Studio. Primary-source lines stay placeholders unless the locator is already in the input, and even then it is recorded only in machine JSON as unverified.

### 6. `shorts-cutter` — Shorts A–D bake brief

Reads VO-timing markdown and optional `CLIP-NOTES`. Writes `shorts/epXX/SHORTS-SHOTLIST.md` with four cuts (A–D). Each cut has a hook line, an in/out (VO line ref and, when a clip note matches, a clip timecode), a CTA beat, and a 9:16 note. Also writes `machine.json` with `"distro_blocked": true`.

Does not render video.

## Agent usage

`distro-pack` and `shorts-cutter` are local Cut helpers. They do not upload, render, call YouTube or Spotify, or unlock Distro. Channel display name is **From Fiction to Fact** (FFTF only).

Machine JSON always has these fields: `episode_id`, `sources`, `fences`, `asset_index`, and `distro_blocked`. `distro_blocked` is the boolean `true`. If it is missing or not true, stop. Do not invent a primary source; fill a description placeholder only from the stamped draft. `sources[].verified` stays false. `{{LONG_FORM_URL}}` is a placeholder, not a live link.

```bash
fftf distro-pack --ep 3 --title "Watergate" \
  --draft samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --thumb path/to/thumb.png \
  -o distro/ep03

fftf shorts-cutter --ep 3 --title "Watergate" \
  --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --clips samples/CLIP-NOTES.md \
  -o shorts/ep03
```

Read `machine.json` in the output directory before any Studio paste.

## Samples

Reference files under `samples/`:

- `ep03-watergate-v1.1-vo-timing-v3.md` — VO-timing markdown for `vo-check` and the optional `--vo` input to `duck-sheet`
- `CLIP-NOTES.md` — clip table notes for `duck-sheet`
- `CUT-AV-DUCK-CUES-2026-09-24.md` — bullet duck-cue sheet for `duck-sheet`

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

## Layout

```
pyproject.toml
src/fftf_tools/
tests/
samples/
```
