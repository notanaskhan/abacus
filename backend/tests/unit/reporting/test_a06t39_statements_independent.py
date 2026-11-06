"""A-06-T39 (ADR-078): independent tests of the statements schema and service (T19, T25), from the
row: an override or N/A reason refused when missing, tie-out 63 of 63 and 62 of 63 with RJE-1 as
the cause, out of date on a new snapshot or approved entry, no client-side arithmetic on AUD-20."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import statements
from abacus.modules.reporting.compute import fs_draft, tie_out

REPO = Path(__file__).resolve().parents[4]
_CTX = cast(AuthContext, SimpleNamespace(tenant=None, tenant_id=uuid4(), user_id=uuid4()))
BENEFITS = "benefits_paid"
YEAR = 2025


def _book(benefits: Decimal) -> tuple[list[tie_out.Value], dict[tuple[str, int], Decimal]]:
    """63 traced figures (24 + 15 + 24, as the row's Northwind v3): one is Benefits paid."""
    keys = [BENEFITS, *(f"line_{n}" for n in range(62))]
    values = [
        tie_out.Value(k, k, YEAR, benefits if k == BENEFITS else Decimal(n + 1), "tb_linked")
        for n, k in enumerate(keys)
    ]
    expected = {(k, YEAR): Decimal("812650.00") if k == BENEFITS else Decimal(n + 1)
                for n, k in enumerate(keys)}  # fmt: skip
    return values, expected


def test_v3_ties_63_of_63() -> None:
    values, expected = _book(Decimal("812650.00"))
    result = tie_out.tie_out(values, expected, ())
    assert (result.tied, result.total) == (63, 63)
    assert result.off == ()


def test_v1_ties_62_of_63_with_rje1_as_the_cause() -> None:
    values, expected = _book(Decimal("797800.00"))
    effects = (tie_out.EntryEffect("RJE-1", "6000", Decimal("14850.00")),)
    values[0] = tie_out.Value(
        BENEFITS, BENEFITS, YEAR, Decimal("797800.00"), "tb_linked", (), ("6000",)
    )
    result = tie_out.tie_out(values, expected, effects)
    assert (result.tied, result.total) == (62, 63)
    assert [(o.line_key, o.off_by, o.cause) for o in result.off] == [
        (BENEFITS, Decimal("-14850.00"), "RJE-1")
    ]


@pytest.mark.parametrize("reason", [None, "", "   "])
async def test_an_na_without_a_reason_is_refused_before_anything_is_stored(
    reason: str | None,
) -> None:
    # The tenant is None: reaching the database would raise something else.
    with pytest.raises(statements.ReasonRequired):
        await statements.answer_item(_CTX, uuid4(), "k", "na", reason, None, 1)


def _version(snapshot: object, adjustments: str) -> dict[str, object]:
    return {
        "engagement_id": uuid4(),
        "source_snapshot_id": snapshot,
        "adjustments_hash": adjustments,
    }


async def _source_with(
    monkeypatch: pytest.MonkeyPatch, snapshot: object, refs: tuple[str, ...]
) -> None:
    async def source(_tenant: object, _engagement: object) -> SimpleNamespace:
        recorded = [SimpleNamespace(ref=r) for r in refs]
        return SimpleNamespace(version_id=snapshot, entries=SimpleNamespace(recorded=recorded))

    monkeypatch.setattr(statements, "_source", source)


async def test_a_version_on_the_current_snapshot_and_entries_is_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = uuid4()
    await _source_with(monkeypatch, snapshot, ("AJE-1",))
    version = _version(snapshot, fs_draft.adjustments_hash(["AJE-1"]))
    assert await statements.is_out_of_date(_CTX.tenant, version) is False


async def test_a_new_snapshot_makes_it_out_of_date(monkeypatch: pytest.MonkeyPatch) -> None:
    await _source_with(monkeypatch, uuid4(), ("AJE-1",))
    version = _version(uuid4(), fs_draft.adjustments_hash(["AJE-1"]))
    assert await statements.is_out_of_date(_CTX.tenant, version) is True


async def test_a_newly_approved_entry_makes_it_out_of_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = uuid4()
    await _source_with(monkeypatch, snapshot, ("AJE-1", "RJE-1"))
    version = _version(snapshot, fs_draft.adjustments_hash(["AJE-1"]))
    assert await statements.is_out_of_date(_CTX.tenant, version) is True


def test_aud20_does_no_arithmetic_on_a_figure() -> None:
    screen = (REPO / "apps/web/src/screens/AUD-20/Statements.tsx").read_text()
    assert ".reduce(" not in screen
    assert "parseFloat" not in screen
