import json
import socket
from pathlib import Path

from click.testing import CliRunner

from fftf_tools.cli import main
from fftf_tools.distro_runners import (
    run_distro_podcast,
    run_distro_podcast_extended,
    run_distro_shorts,
    run_distro_status,
    run_distro_yt_long,
)
from fftf_tools.schema import validate_machine
from tests.fixtures.episode_pack import build_episode_pack


def test_status_dry_run_happy(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    out = tmp_path / "distro"
    result = run_distro_status(pack, out_dir=out)
    assert result["ok"] is True, result["blockers"]
    assert result["distro_blocked"] is True
    assert result["published"] is False
    assert result["uploads"] is False
    assert result["ordered_waves"] == ["yt-long", "shorts", "podcast"]
    assert "podcast-extended" not in result["ordered_waves"]
    assert "podcast-extended" in result["separate_waves"]
    assert result["display_name_lock"] == "From Fiction to Fact"
    assert result["ingest"]["pc_pack_path"]
    assert result["ingest"]["creators_session"] == "desk-session"
    assert result["ingest"]["box_studio_only"] is False
    assert result["ingest"]["checklist"]
    assert result["ingest"]["size_caps_ok"] is True
    assert any(row["id"] == "yt_long" and row["ok"] for row in result["ingest"]["checklist"])
    assert result["runners"]["yt-long"]["ready"] is True
    assert result["runners"]["podcast"]["ready"] is True
    assert result["runners"]["shorts"]["waiting"] == ["gate_shorts_longform_url"]
    assert result["runners"]["podcast-extended"]["separate_go"] is True
    assert result["runners"]["podcast-extended"]["ready"] is False
    text = (out / "distro" / "status.md").read_text(encoding="utf-8")
    assert "distro_blocked: true" in text
    assert "does not publish" in text
    assert "PC pack" in text
    machine = result["machine"]
    assert machine["distro_blocked"] is True
    assert validate_machine(machine) == []


def test_distro_refuses_gates(tmp_path: Path):
    cases = (
        ({"script_stamped": False}, "gate_script_unstamped"),
        ({"drop_live_thumbs": True}, "gate_thumb_live_missing"),
        ({"wording_hash_override": "0" * 64}, "gate_wording_hash_mismatch"),
        ({"blank_license": True}, "gate_license_missing"),
        ({"display_name": "Some Other Show"}, "gate_display_name"),
    )
    for kwargs, code in cases:
        pack = build_episode_pack(tmp_path / code, **kwargs)
        result = run_distro_status(pack, out_dir=tmp_path / f"out-{code}")
        assert result["ok"] is False
        assert code in result["blockers"]
        assert result["published"] is False
        assert result["distro_blocked"] is True


def test_shorts_require_longform_url_and_do_not_upload(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    refused = run_distro_shorts(pack, out_dir=tmp_path / "no-url")
    assert refused["ok"] is False
    assert "gate_shorts_longform_url" in refused["blockers"]
    assert refused["published"] is False
    linked = run_distro_shorts(
        pack,
        longform_url="https://example.com/episodes/ep05",
        apply=True,
        out_dir=tmp_path / "linked",
    )
    assert linked["ok"] is True, linked["blockers"]
    assert linked["applied"] is True
    assert linked["published"] is False
    assert linked["platform_called"] is False
    assert linked["distro_blocked"] is True
    room = json.loads((tmp_path / "linked" / "distro" / "room-report.json").read_text(encoding="utf-8"))
    assert room["published"] is False
    assert room["urls"]["yt_long"] is None
    assert room["distro_blocked"] is True


def test_yt_long_apply_stays_blocked(tmp_path: Path, monkeypatch):
    def _refuse(self, *args, **kwargs):
        raise AssertionError(f"socket connect {args}")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("create_connection")))
    pack = build_episode_pack(tmp_path / "pack")
    result = run_distro_yt_long(pack, apply=True, out_dir=tmp_path / "yt")
    assert result["ok"] is True, result["blockers"]
    assert result["published"] is False
    assert result["uploads"] is False
    assert result["platform_called"] is False
    assert result["distro_blocked"] is True
    plan = json.loads((tmp_path / "yt" / "distro" / "yt-long.json").read_text(encoding="utf-8"))
    assert plan["published"] is False
    assert plan["platform_called"] is False


def test_podcast_excludes_extended_and_extended_needs_its_own_go(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    podcast = run_distro_podcast(pack, out_dir=tmp_path / "pod")
    assert podcast["ok"] is True, podcast["blockers"]
    assert podcast["includes_extended"] is False
    assert podcast["extended_path"] is None
    assert podcast["cover_locked"] is True
    assert podcast["published"] is False

    extended = run_distro_podcast_extended(pack, out_dir=tmp_path / "ext")
    assert extended["ok"] is False
    assert "gate_podcast_extended_go" in extended["blockers"]
    assert extended["in_yt_wave"] is False

    main_go = pack / "distro-go.json"
    still = run_distro_podcast_extended(pack, go_path=main_go, out_dir=tmp_path / "ext-main-go")
    assert "gate_podcast_extended_go" in still["blockers"]

    ready_pack = build_episode_pack(tmp_path / "ready", with_extended=True, extended_go=True)
    ready = run_distro_podcast_extended(ready_pack, out_dir=tmp_path / "ext-ready")
    assert ready["ok"] is True, ready["blockers"]
    assert ready["separate_go"] is True
    assert ready["in_yt_wave"] is False
    assert ready["published"] is False
    status = run_distro_status(ready_pack, out_dir=tmp_path / "status-ready")
    assert status["ok"] is True, status["blockers"]
    assert "podcast-extended" not in status["ordered_waves"]
    assert status["runners"]["podcast-extended"]["ready"] is True


def test_distro_cli_status(tmp_path: Path):
    pack = build_episode_pack(tmp_path / "pack")
    out = tmp_path / "out"
    runner = CliRunner()
    help_result = runner.invoke(main, ["distro", "--help"])
    assert help_result.exit_code == 0
    for name in ("status", "yt-long", "shorts", "podcast", "podcast-extended"):
        assert name in help_result.output
    assert "--publish" not in help_result.output
    result = runner.invoke(main, ["distro", "status", "--pack", str(pack), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert "distro_blocked: true" in result.output
    data = json.loads((out / "distro" / "status.json").read_text(encoding="utf-8"))
    assert data["published"] is False
    refused = runner.invoke(
        main,
        ["distro", "shorts", "--pack", str(pack), "-o", str(tmp_path / "shorts"), "--apply"],
    )
    assert refused.exit_code == 1
    assert "gate_shorts_longform_url" in refused.output


def test_distro_modules_do_not_import_network_clients():
    root = Path(__file__).resolve().parents[1] / "src" / "fftf_tools"
    text = (root / "distro_runners.py").read_text(encoding="utf-8")
    for banned in ("urllib.request", "http.client", "requests", "import socket", "googleapiclient"):
        assert banned not in text
