"""Q-02-T32 (ADR-167 Enforcement): CLS-001 keeps the classification flags inside `classified()`
and the path helpers. Outside `kernel/classification.py`, product code never spells a flag key."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.quality import banned_patterns as bp

RULE = "CLS-001"
MODULE = "src/abacus/modules/organisations/contract.py"
KERNEL = "src/abacus/kernel/classification.py"
TEST_FILE = "tests/unit/x/test_y.py"


def _count(root: Path, rel: str, source: str) -> int:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return len([v for v in bp.scan(root) if v.rule_id == RULE and v.path == rel])


@pytest.mark.parametrize("key", ["x-tri", "x-phi", "x-pii-kind"])
def test_a_hand_set_flag_is_refused(tmp_path: Path, key: str) -> None:
    extra = f'{{"cls": "restricted", "{key}": 1}}'
    source = f"from pydantic import Field\nx = Field(json_schema_extra={extra})\n"
    assert _count(tmp_path, MODULE, source) == 1


def test_a_hand_read_flag_is_refused(tmp_path: Path) -> None:
    source = (
        'def kind(schema: dict[str, object]) -> object:\n    return schema.get("x-pii-kind")\n'
    )
    assert _count(tmp_path, MODULE, source) == 1


def test_the_kernel_and_tests_may_spell_the_keys(tmp_path: Path) -> None:
    assert _count(tmp_path, KERNEL, 'TRI_KEY = "x-tri"\n') == 0
    assert _count(tmp_path, TEST_FILE, 'assert "x-tri"\n') == 0


def test_classified_with_flags_is_fine(tmp_path: Path) -> None:
    source = (
        "from typing import Annotated\n"
        "from abacus.kernel.classification import classified\n"
        'T = Annotated[str, classified("restricted", pii_kind="tin")]\n'
    )
    assert _count(tmp_path, MODULE, source) == 0


def test_the_repository_is_clean() -> None:
    assert [v for v in bp.scan() if v.rule_id == RULE] == []
