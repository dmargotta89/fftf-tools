# fftf-tools

Local production helpers for **From Fiction to Fact** (FFTF short form only).

These commands stay on the production desk. They do not publish, unlock Distro, call YouTube or Spotify, or spend money. Every pipeline command writes `distro_blocked: true` and cannot set it false.

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

### 7. `brief-pack` — research skeleton

Writes `{episode-id}-brief.md` (Fiction / Pushback / Reveal / Aftermath, sources, timeline, risk notes), `ASSET-HUNT.md` (public-domain and government targets; skip network and Hollywood), and `{episode-id}.machine.json`.

Source URLs are `PLACEHOLDER`. The tool does not invent primary-source URLs. An agent fills research later.

```bash
fftf brief-pack --topic "Glomar and Project Azorian" --year-window "1974" --episode-id ep04-glomar-azorian -o ./ep04
```

### 8. `claim-gate` — verifier

Reads a brief, outline, draft, or narration. Optional `--sources`, `--fences`, and `--narration`. Writes `reviews/<stem>-verifier.md` plus a machine block.

Verdict is `PASS`, `PASS_WITH_EDITS`, or `FAIL` (exit 1). Hard fails: the cartoon/spine vocab fence on spoken lines, an unsourced quotation, claimed facts with no real source URL, a broken fence, or a draft that does not match narration. Fence rules and source lists are not spoken, so naming a locked word there is not itself a hit.

```bash
fftf claim-gate ./ep04/ep04-glomar-azorian-brief.md -o ./ep04/claim-1
```

### 9. `script-strip` — draft, narration, VO-timing, delta

Reads a stamped brief and a locks JSON (`vocab`, `naming`, `fences`, `cold_open_rules`, optional `envelope`). Writes `draft.md`, `narration-only.md`, `vo-timing.md` (`[p]` / `[P]`), `delta.md`, and a machine block.

v1 fills a real structure with TODO markers instead of a full documentary. Spoken word counts are counted from those files. Spoken files never contain the locked words.

```bash
fftf script-strip ./ep04/ep04-glomar-azorian-brief.md --locks ./locks.json -o ./ep04/script
```

### 10. `picture-sync` — shot map and duck schedule

Reads VO-timing plus CLIP-NOTES or duck cues. Reuses the `duck-sheet` parser. Writes `SHOT-MAP.md`, `DUCK-SCHEDULE.json`, `PICTURE-SYNC-CHECK.md`, and a machine block with `ducks`, `sync_flags`, and `qc_gates`.

v1 pairs ducks to beats in list order. It does not fetch media.

```bash
fftf picture-sync ./ep04/script/vo-timing.md samples/CLIP-NOTES.md -o ./ep04/picture
```

### 11. `thumb-pack` — title options

Takes title candidates A/B/C and an optional still. Writes YouTube 1280×720 and Instagram 1080×1350 CONTAIN+pad PNGs, `thumb-brief.md` (FIXED checklist), and a machine block with `options` (`id`, `title_text`, `yt_md5`, `ig_md5`) and `safe_zone_ok`.

No external generative API. With no still, Pillow draws high-contrast title cards on a dark field. Safe zone matches `thumb-safe` (side 10%, top 12%, bottom 12%).

```bash
fftf thumb-pack --episode-id ep04-glomar-azorian --title-a "The ship" --title-b "The cover" --title-c "The files" -o ./ep04/thumb
```

## Shared machine contract

Blocks are built with `fftf_tools.machine.machine_block` and checked against `schemas/machine-contract.schema.json`. Pipeline commands go through `fftf_tools.schema`, which calls `machine_block` and `write_machine_json` instead of writing a second shape.

Top-level fields are `episode_id`, `sources`, `fences`, `asset_index`, and `distro_blocked`. `distro_blocked` is always `true`. `sources[].verified` is always `false`.

A source may carry Wave 2 fields (`id`, `locator`, `label`, `origin`, `verified`) and pipeline fields (`n`, `url`) on the same object. `locator` and `url` are the same string. Unfilled research stays `PLACEHOLDER`. Tools do not invent URLs.

A fence may carry `text` and `locked` together with `rule` and `status` (`held`, `broken`, or `unknown`). Base fences `no-publish`, `no-distro`, `no-platform-api`, and `no-invented-sources` stay held because the tools enforce them.

An asset may be `{role, path}` or, when a picture beat is known, also `beat`, `license`, and `sha256`. Beats are `fiction`, `pushback`, `reveal`, `aftermath`, `cold_open`. Licenses are `PD`, `gov`, `cia`, `other`.

```json
{
  "episode_id": "ep04-glomar-azorian",
  "sources": [{"id": "s1", "n": 1, "locator": "PLACEHOLDER", "url": "PLACEHOLDER", "label": "primary document", "verified": false}],
  "fences": [{"id": "no-publish", "text": "Do not publish.", "rule": "Do not publish.", "locked": true, "status": "held"}],
  "asset_index": [{"role": "reveal", "path": "clips/example.mp4", "beat": "reveal", "license": "PD", "sha256": ""}],
  "distro_blocked": true
}
```

`--json` prints that block on stdout. The channel display name is **From Fiction to Fact**. FFTF is the short form only. Spoken narration must not contain the words cartoon or spine.

## Agent chain

Run the commands in this order. Claim-gate runs twice: once on the brief, again after the strip.

```bash
fftf brief-pack --topic "Glomar and Project Azorian" --year-window "1974" --episode-id ep04-glomar-azorian -o ./ep04
fftf claim-gate ./ep04/ep04-glomar-azorian-brief.md -o ./ep04/claim-1
fftf script-strip ./ep04/ep04-glomar-azorian-brief.md --locks ./locks.json -o ./ep04/script
fftf claim-gate ./ep04/script/draft.md --narration ./ep04/script/narration-only.md -o ./ep04/claim-2
fftf picture-sync ./ep04/script/vo-timing.md samples/CLIP-NOTES.md -o ./ep04/picture
fftf thumb-pack --episode-id ep04-glomar-azorian --title-a "The ship" --title-b "The cover" --title-c "The files" -o ./ep04/thumb
```

A fresh skeleton usually returns `PASS_WITH_EDITS` because TODOs and `PLACEHOLDER` URLs are still open. That is not a Distro unlock. None of these commands stamp Distro, publish, or call YouTube or Spotify.

Example locks file:

```json
{
  "vocab": ["cartoon", "spine"],
  "naming": ["From Fiction to Fact"],
  "fences": [],
  "cold_open_rules": "Date, place, and stake. No verdict yet.",
  "envelope": {"min_words": 1200, "max_words": 1800}
}
```

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
schemas/machine-contract.schema.json
src/fftf_tools/
tests/
samples/
```
