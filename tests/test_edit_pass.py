import json
from pathlib import Path

from click.testing import CliRunner
from PIL import Image

from fftf_tools.cli import main
from fftf_tools.edit_pass import run_edit_pass, run_edit_status, sample_indices, select_source_ref, usable_frame_indices
from fftf_tools.episode_pack import hash_path
from fftf_tools.schema import validate_machine
from tests.fixtures.episode_pack import NOTES, build_episode_pack


def test_sampler_never_includes_frame_zero():
    assert 0 not in usable_frame_indices(24)
    assert 0 not in sample_indices(24, 24)
    assert usable_frame_indices(24)[0] != 0


def test_pretty_frame_zero_is_not_the_ref(tmp_path: Path):
    frames = []
    for index in range(12):
        path = tmp_path / f"frame_{index:03d}.png"
        color = (80, 110, 140) if index in {0, 4, 5, 6, 7} else (0, 0, 0)
        if index == 11:
            color = (255, 255, 255)
        image = Image.new("RGB", (64, 36), color)
        image.save(path)
        frames.append(path)
    chosen = select_source_ref(frames, sequence=True)
    assert chosen["blocker"] is None
    assert chosen["frame_index"] != 0
    assert 0 not in chosen["sampled_indices"]


def test_all_black_sequence_blocks(tmp_path: Path):
    frames = []
    for index in range(8):
        path = tmp_path / f"frame_{index:03d}.png"
        Image.new("RGB", (32, 32), (0, 0, 0)).save(path)
        frames.append(path)
    chosen = select_source_ref(frames, sequence=True)
    assert chosen["frame_index"] is None
    assert chosen["blocker"] == "no_valid_ref_frame"


def test_edit_pass_dry_run_happy(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    vo = pack / "vo" / "narration.wav"
    narration = pack / "vo" / "narration-only.md"
    caption = pack / "caption_safe.json"
    thumb = pack / "thumbs" / "ep05-A-LIVE.png"
    before = {
        "vo": hash_path(vo),
        "narration": hash_path(narration),
        "caption": hash_path(caption),
        "thumb": hash_path(thumb),
    }
    out = tmp_path / "edit"
    result = run_edit_pass(pack, out_dir=out)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["distro_blocked"] is True
    assert result["published"] is False
    assert result["uploads"] is False
    assert result["blockers"] == []
    assert result["ref_frame_index"] not in (None, 0)
    assert 0 not in result["sampled_indices"]
    assert not list(out.glob("masters/*.mp4"))
    progress = json.loads((out / "edit" / "progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "succeeded"
    assert progress["stage"] == "write_report"
    assert progress["pct"] == 100
    assert progress["distro_blocked"] is True
    assert progress["artifacts"]["master"] is None
    report = (out / "edit" / "report.md").read_text(encoding="utf-8")
    assert "From Fiction to Fact" in report
    assert "frame 0" in report.lower() or "Frame 0" in report
    grade = json.loads((out / "edit" / "grade.json").read_text(encoding="utf-8"))
    assert grade["anchor"]["frame_index"] != 0
    assert 0 not in grade["anchor"]["sampled_indices"]
    cards = json.loads((out / "edit" / "lower-thirds.json").read_text(encoding="utf-8"))
    assert cards["notes_used"] is False
    assert NOTES not in [card["text"] for card in cards["cards"]]
    assert {card["source"] for card in cards["cards"]} <= {"caption_safe", "quote_card"}
    assembly = json.loads((out / "edit" / "assembly-pack.json").read_text(encoding="utf-8"))
    assert assembly["distro_blocked"] is True
    assert assembly["masters"]["longform"]["path"] is None
    assert assembly["masters"]["podcast_extended"]["separate_go"] is True
    assert "size_checklist" in assembly
    assert assembly["picture_qc"]["passed"] is False
    machine = json.loads((out / "ep05.machine.json").read_text(encoding="utf-8"))
    assert machine["distro_blocked"] is True
    assert validate_machine(machine) == []
    assert machine["sources"]
    for source in machine["sources"]:
        assert source["verified"] is False
        assert source["url"] == source["locator"]
        assert source["n"] >= 1
    for fence in machine["fences"]:
        assert fence["rule"]
        assert fence["text"]
        assert fence["status"] in {"held", "broken", "unknown"}
    licensed = [asset for asset in machine["asset_index"] if asset.get("license")]
    assert licensed
    assert all(asset.get("sha256") for asset in licensed)
    assert any(asset["license"] == "PD" for asset in licensed)
    assert hash_path(vo) == before["vo"]
    assert hash_path(narration) == before["narration"]
    assert hash_path(caption) == before["caption"]
    assert hash_path(thumb) == before["thumb"]
    status = run_edit_status(str(out))
    assert status["ok"] is True
    assert status["job_id"] == result["job_id"]


def test_edit_pass_dry_run_refuses_the_same_gates(tmp_path: Path):
    cases = (
        ({"script_stamped": False}, "gate_script_unstamped"),
        ({"drop_live_thumbs": True}, "gate_thumb_live_missing"),
        ({"wording_hash_override": "0" * 64}, "gate_wording_hash_mismatch"),
        ({"blank_license": True}, "gate_license_missing"),
        ({"caption_equals_notes": True}, "gate_caption_safe_equals_notes"),
    )
    for kwargs, code in cases:
        pack = build_episode_pack(tmp_path / code, **kwargs)
        out = tmp_path / f"dry-{code}"
        result = run_edit_pass(pack, out_dir=out)
        assert result["dry_run"] is True
        assert result["ok"] is False
        assert result["applied"] is False
        assert code in result["blockers"]
        assert result["distro_blocked"] is True
        assert result["published"] is False
        assert not list(out.glob("masters/*.mp4"))
        progress = json.loads((out / "edit" / "progress.json").read_text(encoding="utf-8"))
        assert progress["status"] == "blocked"
        assert progress["dry_run"] is True
        assert code in progress["blockers"]
        machine = json.loads((out / "ep05.machine.json").read_text(encoding="utf-8"))
        assert machine["distro_blocked"] is True
        assert validate_machine(machine) == []


def test_edit_pass_apply_writes_master_and_leaves_vo(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    vo = pack / "vo" / "narration.wav"
    before = hash_path(vo)
    out = tmp_path / "edit"
    result = run_edit_pass(pack, apply=True, out_dir=out)
    assert result["ok"] is True, result["blockers"]
    assert result["published"] is False
    assert result["distro_blocked"] is True
    master = out / "masters" / "ep05-edit-v1.mp4"
    assert master.is_file()
    assert master.stat().st_size > 500
    assert hash_path(vo) == before
    progress = json.loads((out / "edit" / "progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "succeeded"
    assert progress["artifacts"]["master"]
    assert progress["backend"] == "ffmpeg"
    burned = (out / "edit" / "render" / "lower-third.txt").read_text(encoding="utf-8") if (out / "edit" / "render" / "lower-third.txt").is_file() else ""
    assert NOTES not in burned


def test_edit_pass_refuses_bad_packs(tmp_path: Path):
    cases = (
        ({"script_stamped": False}, "gate_script_unstamped"),
        ({"drop_live_thumbs": True}, "gate_thumb_live_missing"),
        ({"wording_hash_override": "0" * 64}, "gate_wording_hash_mismatch"),
        ({"blank_license": True}, "gate_license_missing"),
        ({"caption_equals_notes": True}, "gate_caption_safe_equals_notes"),
    )
    for kwargs, code in cases:
        pack = build_episode_pack(tmp_path / code, **kwargs)
        out = tmp_path / f"out-{code}"
        result = run_edit_pass(pack, apply=True, out_dir=out)
        assert result["ok"] is False
        assert code in result["blockers"]
        assert result["distro_blocked"] is True
        assert result["published"] is False
        assert not list(out.glob("masters/*.mp4"))
        progress = json.loads((out / "edit" / "progress.json").read_text(encoding="utf-8"))
        assert progress["status"] == "blocked"
        assert code in progress["blockers"]


def test_resolve_does_not_silently_downgrade(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    blocked = run_edit_pass(pack, backend="resolve", out_dir=tmp_path / "blocked")
    assert blocked["ok"] is False
    assert blocked["backend"] == "resolve"
    assert blocked["fallback_from"] is None
    assert "resolve_unavailable" in blocked["blockers"]
    assert not list((tmp_path / "blocked").glob("masters/*.mp4"))
    report = (tmp_path / "blocked" / "edit" / "report.md").read_text(encoding="utf-8")
    assert "was not substituted" in report or "Refusing" in report or "resolve_unavailable" in report

    fallback = run_edit_pass(
        pack,
        backend="resolve",
        fallback_ffmpeg=True,
        out_dir=tmp_path / "fallback",
    )
    assert fallback["ok"] is True
    assert fallback["backend"] == "ffmpeg"
    assert fallback["fallback_from"] == "resolve"
    assert fallback["dry_run"] is True
    assert not list((tmp_path / "fallback").glob("masters/*.mp4"))


def test_edit_pass_cli_dry_run(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    out = tmp_path / "cli"
    runner = CliRunner()
    result = runner.invoke(main, ["edit-pass", "--pack", str(pack), "-o", str(out), "--json"])
    assert result.exit_code == 0, result.output
    assert "distro_blocked: true" in result.output
    payload = json.loads(result.stdout)
    assert payload["distro_blocked"] is True
    assert payload["dry_run"] is True
    status = runner.invoke(main, ["edit-pass", "status", "--job", str(out)])
    assert status.exit_code == 0, status.output
    assert "distro_blocked: true" in status.output


def test_script_verifier_frame_have_no_distro_path():
    root = Path(__file__).resolve().parents[1] / "src" / "fftf_tools"
    for name in ("script_strip.py", "claim_gate.py", "thumb_pack.py", "brief_pack.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "distro_runners" not in text
        assert "run_distro_" not in text
    edit = (root / "edit_pass.py").read_text(encoding="utf-8")
    assert "run_distro_" not in edit
    assert "urllib.request" not in edit
    assert "socket" not in edit
