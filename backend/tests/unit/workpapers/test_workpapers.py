"""SPEC-308 (TASK-319): the formula engine, the content hash, status and sign-off rules."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.kernel._statuses import AuditSectionStatus
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review.api import states_of
from abacus.modules.workpapers.formulas import evaluate, parse_number
from abacus.modules.workpapers.service import (
    CellEdit,
    WorkpaperInvalid,
    clean_edits,
    content_hash,
    content_of,
    status_of,
)


def test_ac3_numbers_formulas_and_sums_are_computed_in_decimal() -> None:
    values = evaluate(
        {
            "B2": "1,250.10",
            "B3": "(250.10)",
            "B4": "Cash",
            "B5": "=SUM(B2:B4)",
            "C5": "=B5*2/4-(1+1)",
            "D1": "=0.1+0.2",
        }
    )
    assert values["B2"] == Decimal("1250.10")
    assert values["B3"] == Decimal("-250.10")
    assert values["B4"] == "Cash"
    assert values["B5"] == Decimal("1000.00")
    assert values["C5"] == Decimal("498")
    assert values["D1"] == Decimal("0.3")


@pytest.mark.parametrize(
    ("raws", "key", "code"),
    [
        ({"A1": "=A2", "A2": "=A1"}, "A1", "#CYCLE!"),
        ({"A1": "=A1+1"}, "A1", "#CYCLE!"),
        ({"A1": "=1/0"}, "A1", "#DIV/0!"),
        ({"A1": "=1+"}, "A1", "#ERR!"),
        ({"A1": "=B1+1", "B1": "text"}, "A1", "#ERR!"),
        ({"A1": "=SUM(A2:ZZ9999)"}, "A1", "#REF!"),
        ({"A1": "=1/0", "A2": "=A1+1"}, "A2", "#DIV/0!"),
    ],
)
def test_ac3_errors_are_values(raws: dict[str, str], key: str, code: str) -> None:
    assert evaluate(raws)[key] == code


def test_ac3_an_empty_reference_counts_as_zero() -> None:
    assert evaluate({"A1": "=B9+5"})["A1"] == Decimal(5)


def test_ac3_plain_text_is_not_a_number() -> None:
    assert parse_number("12 units") is None
    assert parse_number("$1,000") == Decimal(1000)


def test_ac3_edits_are_validated() -> None:
    assert clean_edits([CellEdit("A1", "  ", ("footed", "agreed", "footed"))]) == [
        CellEdit("A1", None, ("agreed", "footed"))
    ]
    with pytest.raises(WorkpaperInvalid):
        clean_edits([CellEdit("a1", "x", ())])
    with pytest.raises(WorkpaperInvalid):
        clean_edits([CellEdit("A1", "x", ("ticked",))])
    with pytest.raises(WorkpaperInvalid):
        clean_edits([CellEdit("A1", "x", ()), CellEdit("A1", "y", ())])


def _cell(key: str, raw: str | None, marks: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(cell_key=key, raw=raw, tickmarks=marks or [])


def test_ac5_the_hash_covers_cells_tickmarks_and_citations_only() -> None:
    a = content_of([_cell("A1", "1"), _cell("B1", None)], [])  # type: ignore[list-item]  # SimpleNamespace stands in for rows
    b = content_of([_cell("A1", "1")], [])  # type: ignore[list-item]  # SimpleNamespace stands in for rows
    assert content_hash(a) == content_hash(b)
    ticked = content_of([_cell("A1", "1", ["footed"])], [])  # type: ignore[list-item]  # SimpleNamespace stands in for rows
    assert content_hash(ticked) != content_hash(b)
    cited = content_of(
        [_cell("A1", "1")],  # type: ignore[list-item]  # SimpleNamespace stands in for rows
        [SimpleNamespace(cell_key="A1", evidence_version_id=uuid4(), locator=None)],  # type: ignore[list-item]  # SimpleNamespace stands in for rows
    )
    assert content_hash(cited) != content_hash(b)


def _signed(level: int, digest: str, by: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        level=level, signed_by=by or uuid4(), created_at=datetime.now(UTC), content_hash=digest
    )


def test_ac5_status_follows_the_highest_current_level_and_staleness_wins() -> None:
    h = "a" * 64
    assert status_of(False, states_of([], h)) == AuditSectionStatus.NOT_STARTED
    assert status_of(True, states_of([], h)) == AuditSectionStatus.IN_PROGRESS
    assert status_of(True, states_of([_signed(1, h)], h)) == AuditSectionStatus.PREPARED  # type: ignore[list-item]  # SimpleNamespace stands in for rows
    rows = [_signed(2, h), _signed(1, h)]
    assert status_of(True, states_of(rows, h)) == AuditSectionStatus.REVIEWED  # type: ignore[arg-type]  # SimpleNamespace stands in for rows
    rows = [_signed(4, h), _signed(2, h), _signed(1, h)]
    assert status_of(True, states_of(rows, h)) == AuditSectionStatus.SIGNED_OFF  # type: ignore[arg-type]  # SimpleNamespace stands in for rows
    changed = states_of(rows, "b" * 64)  # type: ignore[arg-type]  # SimpleNamespace stands in for rows
    assert all(s.stale for s in changed if s.signed_by)
    assert status_of(True, changed) == AuditSectionStatus.CHANGED_AFTER_SIGNOFF


def test_ac5_the_agent_signs_nothing_and_each_level_has_its_signers() -> None:
    def allowed(action: str) -> set[str]:
        return {r for r, d in RULES[action].decisions.items() if d == "allow"}

    for action in ("prepare", "review", "manager", "partner", "eqr"):
        assert "agent" not in allowed(f"sign_off.{action}")
    assert "engagement_partner" not in allowed("sign_off.prepare")
    assert allowed("sign_off.partner") == {"engagement_partner"}
    assert allowed("sign_off.eqr") == {"reviewer"}
    assert "agent" not in allowed("workpaper.edit")
