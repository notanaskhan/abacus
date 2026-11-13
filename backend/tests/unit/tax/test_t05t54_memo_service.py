"""T-05-T54 (TASK-7906; T-05 F9; TXP-01; DEC-4909, DEC-4910): the preparer memo service.

Row acceptance: "Approving the M-2 fix turns the approved memo Stale with 'ending capital 6,860,000
→ 6,866,200', and Regenerate keeps Olivia's edited section."
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from abacus.modules.tax import memo_service as ms
from abacus.modules.tax.memo_drafter import fingerprint_of


def _cells(rows: dict[str, str]) -> dict[str, dict[str, object]]:
    return {
        k: {"t": "decimal" if v.lstrip("-").isdigit() else "text", "v": v} for k, v in rows.items()
    }


RUN_2 = _cells(
    {
        "05!A2": "Meera Shah", "05!B2": "2000000", "05!C2": "0", "05!D2": "0",
        "05!E2": "4866200", "05!F2": "6866200",
        "07!B9": "6860000",
        "06!A2": "1", "06!B2": "Ordinary business income", "06!C2": "4866200",
    }
)  # fmt: skip
AFTER_FIX = {**RUN_2, "07!B9": {"t": "decimal", "v": "6866200"}}


def test_ac_stale_line_names_the_moved_figure() -> None:
    then, now = ms.memo_facts(RUN_2), ms.memo_facts(AFTER_FIX)
    assert fingerprint_of([f.fact for f in then]) != fingerprint_of([f.fact for f in now])
    lines = [line for _, line in ms.moved(then, now)]
    assert lines == ["ending capital 6,860,000 → 6,866,200"]


def test_ac_regenerate_targets_only_affected_sections() -> None:
    assert ms.affected_sections(ms.memo_facts(RUN_2), ms.memo_facts(AFTER_FIX)) == ["capital"]


def test_ac_facts_cite_their_cells_and_sources_quote_them() -> None:
    facts = ms.memo_facts(RUN_2)
    by_handle = {f.fact.handle: f for f in facts}
    assert by_handle["m2_ending"].cells == ("07!B9",)
    assert by_handle["capital_meera_shah"].fact.value == "6,866,200"
    sources = {s.handle: s for s in ms.sources_of("1065", RUN_2, facts)}
    assert sources[ms.handle_of("07!B9")].quote.endswith("!B9 = 6,860,000")


def test_ac_transfers_are_structural_events() -> None:
    [event] = [f for f in ms.memo_facts({}, ["6/30/2025"]) if f.section == "structural_events"]
    assert event.fact.value == "6/30/2025"


def test_ac_preparer_never_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    olivia = uuid.uuid4()
    memo = ms.MemoRow(uuid.uuid4(), uuid.uuid4(), 3, "f" * 64, "a" * 64)

    async def row(*_a: object) -> ms.MemoRow:
        return memo

    async def preparers(*_a: object) -> frozenset[uuid.UUID]:
        return frozenset({olivia})

    class _Ctx:
        user_id = olivia
        tenant = object()

    monkeypatch.setattr(ms, "memo_row", row)
    monkeypatch.setattr(ms, "preparers", preparers)
    with pytest.raises(ms.PreparerCannotApprove):
        asyncio.run(
            ms.sign_memo(
                _Ctx(),  # type: ignore[arg-type] -- only the user and tenant are read
                uuid.uuid4(), level=2, seen_hash="a" * 64,
            )
        )  # fmt: skip


def test_ac_reviewable_registered() -> None:
    from abacus.modules.review.api import reviewable_fact_types

    assert ms.TARGET in reviewable_fact_types()
