"""TASK-333: readers take an upload's newest extraction, by any extractor version. Only upload
processing looks an extraction up by the current version (one extraction per version); bumping
EXTRACTOR_VERSION in TASK-323 made every earlier upload's preview read as empty."""

from __future__ import annotations

from pathlib import Path

EVIDENCE = Path(__file__).parents[3] / "src" / "abacus" / "modules" / "evidence"


def test_only_processing_looks_extractions_up_by_version() -> None:
    pinned = sorted(
        path.name
        for path in EVIDENCE.glob("*.py")
        if "extractor_version=EXTRACTOR_VERSION" in path.read_text()
    )
    assert pinned == ["processing.py"]
