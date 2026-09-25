from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


@pytest.fixture
def samples() -> Path:
    return SAMPLES


@pytest.fixture
def vo_sample(samples: Path) -> Path:
    return samples / "ep03-watergate-v1.1-vo-timing-v3.md"


@pytest.fixture
def clip_notes(samples: Path) -> Path:
    return samples / "CLIP-NOTES.md"


@pytest.fixture
def duck_cues(samples: Path) -> Path:
    return samples / "CUT-AV-DUCK-CUES-2026-09-24.md"
