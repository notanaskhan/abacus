# ac-test-author: p04t38-independent
"""P-04-T38 (TASK-2023; ADR-078; ADR-161 clause 1): field writes go only through `record_value`.

Acceptance (the task row, this half): the suite "fails if a direct cell write bypasses
record_value". A field's value lives in `field_value_versions`; the only code that may insert
into it, or build a `FieldValueVersion` row, is `review/field_values.py` (`record_value`). The
table is insert-only, so an update or delete anywhere is a bypass too.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

SRC: Final = Path(__file__).resolve().parents[3] / "src" / "abacus"
OWNER: Final = SRC / "modules" / "review" / "field_values.py"
# A write by SQL text or by the ORM: INSERT/UPDATE/DELETE naming the table, or the model built,
# inserted or updated.
_SQL: Final = re.compile(
    r"(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+field_value_versions\b", re.IGNORECASE
)
# The model's own `class FieldValueVersion(Base):` line is its definition, not a write.
_ORM: Final = re.compile(
    r"\b(insert|update|delete)\(\s*FieldValueVersion\b|(?<!class )\bFieldValueVersion\("
)


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == OWNER:
            continue
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), start=1):
            if _SQL.search(line) or _ORM.search(line):
                found.append(f"{path.relative_to(SRC)}:{n}: {line.strip()}")
    return found


def test_only_record_value_writes_a_field_version() -> None:
    assert _offenders() == []


def test_the_owner_really_writes_through_one_function() -> None:
    owner = OWNER.read_text(encoding="utf-8")
    assert "async def record_value(" in owner
    assert _ORM.search(owner) or _SQL.search(owner), "record_value no longer writes a version"


def test_the_scan_would_catch_a_bypass(tmp_path: Path) -> None:
    """The pattern itself: a direct insert by text or by the ORM is seen."""
    for bypass in (
        'await s.execute(text("INSERT INTO field_value_versions (seq) VALUES (1)"))',
        "await s.execute(insert(FieldValueVersion).values(seq=1))",
        "s.add(FieldValueVersion(seq=1))",
        'await s.execute(text("UPDATE field_value_versions SET seq = 2"))',
    ):
        assert _SQL.search(bypass) or _ORM.search(bypass), bypass
