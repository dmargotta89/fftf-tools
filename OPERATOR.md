# Operator dry-run

Channel display name is **From Fiction to Fact** (FFTF only). Every command below keeps `distro_blocked: true`. None of them publish, call YouTube or Spotify, or invent a primary source.

Run these from the repo root after `pip install -e ".[dev]"`. Outcomes below are from that dry-run. `pytest -q` passes.

## Samples

```bash
fftf vo-check samples/ep03-watergate-v1.1-vo-timing-v3.md
```

PASS, exit 0. Estimated duration about 11.77 min, inside 8–12. Spoken word count 1539.

```bash
fftf duck-sheet samples/CLIP-NOTES.md -o /tmp/ep03-duck
fftf duck-sheet samples/CUT-AV-DUCK-CUES-2026-09-24.md \
  --vo samples/ep03-watergate-v1.1-vo-timing-v3.md -o /tmp/ep03-cues
```

PASS, exit 0. CLIP-NOTES writes 14 cues. The cut sheet writes 9. `--vo` is accepted; `vo_pause_note` stays `pause VO under clip audio`.

```bash
fftf drive-checklist --ep 3 --title "Watergate" -o /tmp/ep03-drive-checklist.md
```

PASS, exit 0. Writes an unchecked checklist. It does not touch Drive.

```bash
fftf distro-pack --ep 3 --title "Watergate" \
  --draft samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --thumb /tmp/ep03-thumb.png \
  -o /tmp/distro-ep03
```

PASS, exit 0, even if the thumb file is absent. The path is recorded and not uploaded. `DESCRIPTION.md` keeps `PRIMARY SOURCE PLACEHOLDER`. `machine.json` has `distro_blocked: true`. Chapter times are markup estimates, not a bake timeline.

```bash
fftf shorts-cutter --ep 3 --title "Watergate" \
  --vo samples/ep03-watergate-v1.1-vo-timing-v3.md \
  --clips samples/CLIP-NOTES.md \
  -o /tmp/shorts-ep03
```

PASS, exit 0. Writes `SHORTS-SHOTLIST.md` and `machine.json`. It does not render video. Sources copy locators already in the input (`n`, `url`, and `locator` are the same string, `verified` false). Fences include `rule` and `status`.

## Agent chain

A fresh skeleton is `PASS_WITH_EDITS` (exit 0) because TODOs and `PLACEHOLDER` URLs are still open. That is not a Distro unlock. `FAIL` (exit 1) is only when claim-gate's verdict is `FAIL`.

```bash
fftf brief-pack --topic "Glomar and Project Azorian" --year-window "1974" \
  --episode-id ep04-glomar-azorian -o /tmp/ep04
fftf claim-gate /tmp/ep04/ep04-glomar-azorian-brief.md -o /tmp/ep04/claim-1
```

PASS, exit 0. Verdict `PASS_WITH_EDITS`.

```bash
cat > /tmp/locks.json << 'JSON'
{
  "vocab": ["cartoon", "spine"],
  "naming": ["From Fiction to Fact"],
  "fences": [],
  "cold_open_rules": "Date, place, and stake. No verdict yet.",
  "envelope": {"min_words": 1200, "max_words": 1800}
}
JSON
fftf script-strip /tmp/ep04/ep04-glomar-azorian-brief.md --locks /tmp/locks.json -o /tmp/ep04/script
fftf claim-gate /tmp/ep04/script/draft.md \
  --narration /tmp/ep04/script/narration-only.md -o /tmp/ep04/claim-2
```

PASS, exit 0. Spoken word count on this template was 110. Verdict `PASS_WITH_EDITS`. `narration_match` is true. This is not a VO bake.

```bash
fftf picture-sync /tmp/ep04/script/vo-timing.md samples/CLIP-NOTES.md -o /tmp/ep04/picture
```

PASS, exit 0. 14 ducks, order-paired. Expect `duck-duration-window` warn (cues outside 8–20s) and `extra-duck` flags, because the skeleton has fewer VO sections than CLIP-NOTES. Exit stays 0.

```bash
fftf thumb-pack --episode-id ep04-glomar-azorian \
  --title-a "The ship" --title-b "The cover" --title-c "The files" \
  -o /tmp/ep04/thumb
fftf thumb-safe /tmp/ep04/thumb/ep04-glomar-azorian-thumb-A-yt-1280x720.png -o /tmp/thumb-safe.png
```

PASS, exit 0. `safe_zone_ok: true`. Thumb-safe reports 1280×720. No generative API.

## Edit-pass and distro status

There is no pack builder in the CLI. This uses the same gate-clean fixture the tests use. It writes local stand-in media under `/tmp` and does not open a socket.

```bash
python -c "from pathlib import Path; from tests.fixtures.episode_pack import build_episode_pack; build_episode_pack(Path('/tmp/ep05-pack'))"
fftf edit-pass --pack /tmp/ep05-pack -o /tmp/ep05-edit
fftf edit-pass status --job /tmp/ep05-edit
```

PASS, exit 0. Dry-run is the default (`dry-run: true`). Status `succeeded`, stage `write_report`. No `masters/*.mp4`. Reference frame is not frame 0. `distro_blocked: true`.

```bash
python -c "from pathlib import Path; from tests.fixtures.episode_pack import build_episode_pack; build_episode_pack(Path('/tmp/ep05-unstamped'), script_stamped=False)"
fftf edit-pass --pack /tmp/ep05-unstamped -o /tmp/ep05-edit-fail
```

FAIL, exit 1. `status: blocked`, `blocker: gate_script_unstamped`, dry-run still true, no master.

```bash
fftf distro status --pack /tmp/ep05-pack -o /tmp/ep05-distro
```

PASS, exit 0. Gate matrix rows all ok: `verdict`, `wording`, `dual_stamp`, `thumbs`, `caption_safe`, `asset_index`, `picture_qc`, `display_name`, `meta`, `masters`, `ingest`, `authority`. Ordered wave is `yt-long → shorts → podcast`. `podcast-extended` is not in that wave. Shorts are waiting on `gate_shorts_longform_url`. The report says it does not publish.

```bash
fftf distro yt-long --pack /tmp/ep05-pack -o /tmp/ep05-yt
fftf distro podcast --pack /tmp/ep05-pack -o /tmp/ep05-podcast
```

PASS, exit 0. Dry-run. `published` stays false.

```bash
fftf distro shorts --pack /tmp/ep05-pack -o /tmp/ep05-shorts-fail --apply
```

FAIL, exit 1. `blocker: gate_shorts_longform_url`. `--apply` does not upload. `published` is false and `platform_called` is false.

```bash
fftf distro shorts --pack /tmp/ep05-pack \
  --longform-url https://example.com/episodes/ep05 -o /tmp/ep05-shorts
```

PASS, exit 0. The URL is not fetched. Dry-run only.

```bash
fftf distro podcast-extended --pack /tmp/ep05-pack -o /tmp/ep05-ext-fail
```

FAIL, exit 1. `blocker: gate_master_missing` and `blocker: gate_podcast_extended_go`. The main Distro GO is not enough, and this fixture has no extended master. It is not part of the YT wave.

## Wave-3 candidates

These need a new Daniel stamp. Do not build them in this toolkit as it stands.

- Live YouTube or Spotify upload, clearing `distro_blocked`, or auto-stamping Distro. `--apply` writes a local plan or a local master and still does not publish.
- A pack-builder command. The dry-run above borrows `tests.fixtures.episode_pack`.
- `duck-sheet --vo` pause alignment. The flag is accepted; the cue note is still the default pause line.
- DaVinci Resolve deliver. `fftf edit-pass --backend resolve` blocks with `resolve_unavailable` unless `--fallback-ffmpeg` is passed, and that fallback is still a local dry-run unless `--apply` is also passed.
- A full documentary from `script-strip`. v1 is a TODO template (spoken count 110 on the sample chain).
- Picture-sync timecode lock. v1 pairs ducks to beats in list order.
- Generative thumbnail APIs or any spend.
- Inventing primary-source URLs. Unfilled research stays `PLACEHOLDER`. Locators are copied only when they are already in the input, and `verified` stays false.
