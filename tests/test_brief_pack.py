import json
from pathlib import Path

from fftf_tools.brief_pack import run_brief_pack
from fftf_tools.schema import validate_machine
from fftf_tools.vocab import spoken_hits


def test_brief_pack_writes_required_files(tmp_path: Path):
    payload = run_brief_pack(
        topic="Glomar Azorian",
        year_window="1974",
        out_dir=tmp_path,
        episode_id="ep04-glomar-azorian",
        fences=json.dumps(
            [{"id": "no-coup", "rule": "Do not treat a coup as fact.", "status": "unknown"}]
        ),
    )
    brief = tmp_path / "ep04-glomar-azorian-brief.md"
    hunt = tmp_path / "ASSET-HUNT.md"
    machine = tmp_path / "ep04-glomar-azorian.machine.json"
    assert brief.is_file()
    assert hunt.is_file()
    assert machine.is_file()
    text = brief.read_text(encoding="utf-8")
    for section in ("Fiction", "Pushback", "Reveal", "Aftermath", "Sources", "Timeline", "Risk notes"):
        assert f"## {section}" in text
    assert "From Fiction to Fact" in text
    assert "https://" not in text
    assert "https://" not in hunt.read_text(encoding="utf-8")
    assert "Hollywood" in hunt.read_text(encoding="utf-8")
    assert payload["distro_blocked"] is True
    assert payload["episode_id"] == "ep04-glomar-azorian"
    assert payload["sources"]
    assert all(source["url"] == "PLACEHOLDER" for source in payload["sources"])
    assert all(source["locator"] == "PLACEHOLDER" for source in payload["sources"])
    assert all(source["verified"] is False for source in payload["sources"])
    assert any(fence["id"] == "no-coup" for fence in payload["fences"])
    assert spoken_hits(text) == []
    assert validate_machine(json.loads(machine.read_text(encoding="utf-8"))) == []
