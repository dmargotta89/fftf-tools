import json
import re
from pathlib import Path

from fftf_tools.schema import (
    ContractError,
    MachineContract,
    schema_path,
    seal,
    validate_machine,
)


def _valid() -> dict:
    return {
        "episode_id": "ep04-glomar-azorian",
        "sources": [{"n": 1, "url": "PLACEHOLDER", "label": "primary"}],
        "fences": [{"id": "vocab-cartoon", "rule": "Spoken narration must not contain the word cartoon.", "status": "unknown"}],
        "asset_index": [],
        "distro_blocked": True,
    }


def test_schema_file_locks_distro():
    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    assert schema["required"] == ["episode_id", "sources", "fences", "asset_index", "distro_blocked"]
    assert schema["properties"]["distro_blocked"]["const"] is True
    beats = schema["properties"]["asset_index"]["items"]["properties"]["beat"]["enum"]
    assert beats == ["fiction", "pushback", "reveal", "aftermath", "cold_open"]
    assert schema["properties"]["fences"]["items"]["properties"]["status"]["enum"] == [
        "held",
        "broken",
        "unknown",
    ]


def test_validate_accepts_contract_and_rejects_distro_unlock():
    assert validate_machine(_valid()) == []
    unlocked = _valid()
    unlocked["distro_blocked"] = False
    errors = validate_machine(unlocked)
    assert errors
    assert any("distro_blocked" in error for error in errors)
    missing = _valid()
    del missing["distro_blocked"]
    assert any("distro_blocked" in error for error in validate_machine(missing))


def test_validate_rejects_bad_beat_and_verdict():
    bad_beat = _valid()
    bad_beat["asset_index"] = [{"path": "a.mp4", "beat": "thumb", "license": "PD", "sha256": ""}]
    assert any("beat" in error for error in validate_machine(bad_beat))
    bad_verdict = _valid()
    bad_verdict["verdict"] = "OK"
    assert any("verdict" in error for error in validate_machine(bad_verdict))


def test_contract_cannot_be_constructed_unlocked_and_seal_forces_true():
    try:
        MachineContract(episode_id="ep01-test", distro_blocked=False)
        raised = False
    except ContractError:
        raised = True
    assert raised
    payload = _valid()
    payload["distro_blocked"] = False
    sealed = seal(payload)
    assert sealed["distro_blocked"] is True
    round_trip = MachineContract.from_dict(sealed)
    assert round_trip.to_dict()["distro_blocked"] is True


def test_wave2_machine_block_validates_and_verified_stays_false():
    from fftf_tools.machine import BASE_FENCES, machine_block

    block = machine_block(
        episode_id="ep03",
        sources=[{"id": "s1", "locator": "PLACEHOLDER", "label": "primary", "origin": "draft", "verified": False}],
        fences=[dict(item) for item in BASE_FENCES],
        asset_index=[{"role": "thumb", "path": "t.png"}],
    )
    assert validate_machine(block) == []
    marked = _valid()
    marked["sources"] = [{"n": 1, "url": "PLACEHOLDER", "label": "primary", "verified": True}]
    assert any("verified" in error for error in validate_machine(marked))
    sealed = seal(marked)
    assert sealed["distro_blocked"] is True
    assert sealed["sources"][0]["verified"] is False


def test_seal_fills_dual_source_and_fence_fields():
    sealed = seal(
        {
            "episode_id": "ep04-glomar-azorian",
            "sources": [{"id": "s1", "locator": "PLACEHOLDER", "label": "primary"}],
            "fences": [{"id": "no-publish", "text": "Do not publish.", "locked": True}],
            "asset_index": [],
            "distro_blocked": False,
        }
    )
    source = sealed["sources"][0]
    assert source["n"] == 1
    assert source["url"] == "PLACEHOLDER"
    assert source["locator"] == source["url"]
    assert source["verified"] is False
    fence = sealed["fences"][0]
    assert fence["rule"] == "Do not publish."
    assert fence["text"] == "Do not publish."
    assert fence["status"] == "held"
    assert sealed["distro_blocked"] is True
    assert validate_machine(sealed) == []


def test_seal_rejects_a_fence_status_outside_the_enum():
    try:
        seal(
            {
                "episode_id": "ep04-glomar-azorian",
                "sources": [],
                "fences": [{"id": "no-publish", "text": "Do not publish.", "status": "ok"}],
                "asset_index": [],
                "distro_blocked": True,
            }
        )
        raised = False
    except ContractError:
        raised = True
    assert raised


def test_asset_keeps_license_and_digest_without_a_beat():
    from fftf_tools.schema import Asset

    data = Asset(path="clips/hero.png", role="hero", license="PD", sha256="abc").to_dict()
    assert data == {"path": "clips/hero.png", "role": "hero", "license": "PD", "sha256": "abc"}
    with_beat = Asset(path="clips/hero.png", beat="reveal", license="gov", sha256="").to_dict()
    assert with_beat["beat"] == "reveal"
    assert with_beat["license"] == "gov"
    assert with_beat["sha256"] == ""


def test_pipeline_modules_do_not_call_out():
    root = Path(__file__).resolve().parents[1] / "src" / "fftf_tools"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"^\s*(import|from)\s+(requests|urllib|httpx|socket|ftplib)\b", text, re.M) is None
        assert re.search(r"distro_blocked[\"']?\s*[:=]\s*False", text) is None
