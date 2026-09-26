import ast
import json
from pathlib import Path

from fftf_tools.machine import MACHINE_FIELDS, machine_block, write_machine_json

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "fftf_tools"


def test_machine_block_contract_and_lock():
    block = machine_block(
        episode_id="ep03",
        sources=[],
        fences=[],
        asset_index=[],
        distro_blocked=False,
        publish=True,
        upload=True,
        unlock_distro=True,
    )
    for field in MACHINE_FIELDS:
        assert field in block
    assert block["distro_blocked"] is True
    assert block["sources"] == []
    assert block["fences"] == []
    assert block["asset_index"] == []
    assert "publish" not in block
    assert "upload" not in block
    assert "unlock_distro" not in block


def test_write_machine_json_relocks(tmp_path: Path):
    block = machine_block(episode_id="ep03", sources=[{"id": "s1"}])
    block["distro_blocked"] = False
    path = write_machine_json(tmp_path / "machine.json", block)
    raw = path.read_text(encoding="utf-8")
    assert '"distro_blocked": true' in raw
    data = json.loads(raw)
    assert data["distro_blocked"] is True
    assert isinstance(data["sources"], list)
    assert isinstance(data["fences"], list)
    assert isinstance(data["asset_index"], list)


def test_cut_helpers_do_not_import_http_clients():
    banned = {"requests", "httpx", "urllib", "googleapiclient", "spotipy", "socket"}
    for name in ("machine.py", "vo_sections.py", "distro_pack.py", "shorts_cutter.py", "cli.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & banned), f"{name} imports {imported & banned}"
