"""T-05-T41 (TASK-7701; T-05 F5; TXP-06; DEC-4701, DEC-4702): the allocation structure service.

Row acceptance: "Samuel's L3 sign-off approves the structure and starts the re-run, while an agent
or staff approval is refused." The compute is code's (Ridgeline 628,100 per period, Harborview
4,900,000); a preview persists nothing; a draft's version is checked; the agreement reader's
proposal is adopted as Pending approval, never approved.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from abacus.modules.tax import allocation_structure as alloc
from abacus.modules.tax.allocation_structure import (
    Draft,
    DraftRung,
    PartnerFacts,
    PeriodFacts,
    StructureEditorRequired,
    StructureInvalid,
    StructureNotPending,
    compute,
    draft_from_proposal,
    preparer_of,
    rung_params,
)

D = Decimal
GP, SHAH, PSV, PS2, FELD = (uuid.uuid4() for _ in range(5))
OPENING = {GP: D(2), SHAH: D(38), PSV: D(35), FELD: D(25)}
AFTER = {GP: D(2), SHAH: D(38), PSV: D(30), PS2: D(5), FELD: D(25)}


def _periods() -> list[PeriodFacts]:
    first = [PeriodFacts(p, date(2025, 1, 1), date(2025, 6, 30), v) for p, v in OPENING.items()]
    second = [PeriodFacts(p, date(2025, 7, 1), date(2025, 12, 31), v) for p, v in AFTER.items()]
    return first + second


RIDGELINE = Draft(
    kind="straight_percentage",
    method="interim_closing",
    convention="monthly",
    segment_amounts=(D(628100), D(628100)),
    rungs=(DraftRung(1, "straight_pct"),),
)


def test_ridgeline_two_periods_of_628100_and_meera_shah_238678() -> None:
    found = compute(
        RIDGELINE, year=2025, partners=[], periods=_periods(), transfers=[date(2025, 6, 30)]
    )
    assert [p.amount for p in found.periods] == [D(628100), D(628100)]
    assert found.total == D(1256200)
    assert sum(found.totals.values()) == D(1256200)
    shah_p1 = next(r for r in found.results if r.partner_id == SHAH and r.period_key == "p1")
    assert shah_p1.amount == D(238678)  # 38% of 628,100 (TXP-06 a2)
    assert not any(r.partner_id == PS2 and r.period_key == "p1" for r in found.results)
    assert all(found.checks.values())
    assert found.engine_name == "entity.allocation" and len(found.inputs_hash) == 64


def test_interim_closing_reads_04_when_the_draft_names_no_amounts() -> None:
    draft = Draft(kind="straight_percentage", convention="monthly")
    found = compute(
        draft,
        year=2025,
        partners=[],
        periods=_periods(),
        transfers=[date(2025, 6, 30)],
        sheet_amounts=[D(628100), D(628100)],
    )
    assert found.total == D(1256200)
    with pytest.raises(StructureInvalid) as missing:
        compute(draft, year=2025, partners=[], periods=_periods(), transfers=[date(2025, 6, 30)])
    assert missing.value.facts == {"code": "segment_amounts_required"}


def test_harborview_waterfall_distributes_4_900_000_and_plugs_900_000() -> None:
    gp, lp1, lp2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    partners = [
        PartnerFacts(gp, "Harborview GP", "gp", D(100000)),
        PartnerFacts(lp1, "LP one", "lp", D(2400000)),
        PartnerFacts(lp2, "LP two", "lp", D(1500000)),
    ]
    draft = Draft(
        kind="targeted_waterfall",
        income=D(900000),
        rungs=(
            DraftRung(1, "return_of_capital"),
            DraftRung(2, "preferred_return", rung_params("preferred_return", D(8), None)),
            DraftRung(3, "catch_up", rung_params("catch_up", D(20), None)),
            DraftRung(4, "promote", rung_params("promote", D(20), None)),
        ),
    )
    found = compute(draft, year=2025, partners=partners, periods=[], transfers=[])
    assert [p.amount for p in found.periods] == [D(4000000), D(312000), D(78000), D(510000)]
    assert found.distributable == D(4900000)
    assert sum(found.totals.values()) == D(900000)
    assert found.gp_profit_percent == D("20.00")


def test_the_hash_moves_with_the_structure_not_with_its_citations() -> None:
    cited = Draft(**{**RIDGELINE.__dict__, "citation_ids": (uuid.uuid4(),)})
    edited = Draft(**{**RIDGELINE.__dict__, "convention": "semi_monthly"})
    assert RIDGELINE.hash() == cited.hash()
    assert RIDGELINE.hash() != edited.hash()


def test_proration_is_calendar_day_only_and_priorities_are_unique() -> None:
    with pytest.raises(StructureInvalid):
        compute(
            Draft(
                kind="straight_percentage", method="proration", convention="monthly", income=D(100)
            ),
            year=2025,
            partners=[],
            periods=_periods(),
            transfers=[date(2025, 6, 30)],
        )
    with pytest.raises(StructureInvalid):
        compute(
            Draft(
                kind="targeted_waterfall",
                income=D(1),
                rungs=(DraftRung(1, "residual"), DraftRung(1, "promote")),
            ),
            year=2025,
            partners=[],
            periods=[],
            transfers=[],
        )


def test_the_readers_proposal_becomes_a_draft_with_its_citations() -> None:
    cite = uuid.uuid4()
    draft = draft_from_proposal(
        [
            ("structure:kind", "straight_percentage", (cite,)),
            ("structure:method", "interim_closing", ()),
            ("structure:convention", "monthly", (cite,)),
            ("structure:convention_question", "convention", ()),
        ]
    )
    assert (draft.kind, draft.method, draft.convention) == (
        "straight_percentage",
        "interim_closing",
        "monthly",
    )
    assert draft.citation_ids == (cite,)
    assert draft.rungs == (DraftRung(1, "straight_pct"),)
    with pytest.raises(StructureInvalid):
        draft_from_proposal([("structure:kind", "anything_else", ())])


# --- the service: who drafts, who approves, the re-run ------------------------------------------


_TENANT: Any = object()  # Any: a stand-in tenant
_TENANT_ID = uuid.uuid4()


@dataclass
class _Ctx:
    user_id: uuid.UUID
    tenant: Any = _TENANT
    tenant_id: uuid.UUID = _TENANT_ID


def _row(status: str, by: str = "human", actor: str | None = None) -> alloc.StructureRow:
    return alloc.StructureRow(
        id=uuid.uuid4(),
        version_no=1,
        status=status,
        kind="straight_percentage",  # type: ignore[arg-type]
        method="interim_closing",
        convention="monthly",
        income=D(1256200),
        distributable=None,
        proposed_by_kind=by,
        proposal_id=None,
        content_hash="a" * 64,  # type: ignore[arg-type]
        citation_ids=(),
        supersedes_id=None,
        actor_kind="human",
        actor_id=actor or str(uuid.uuid4()),
        engagement_id=uuid.uuid4(),
        work_item_id=uuid.uuid4(),
    )


def test_a_senior_or_staff_draft_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    async def role(tenant: object, engagement: object, user: object) -> str:
        return "senior"

    monkeypatch.setattr(alloc, "engagement_role_of", role)
    with pytest.raises(StructureEditorRequired):
        asyncio.run(
            alloc.save_draft(
                _Ctx(uuid.uuid4()),  # type: ignore[arg-type]
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                year=2025,
                expected_version=0,
                draft=RIDGELINE,
            )
        )


def test_only_a_version_pending_approval_is_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    async def approved(tenant: object, return_id: object) -> list[alloc.StructureRow]:
        return [_row("approved")]

    monkeypatch.setattr(alloc, "versions", approved)
    with pytest.raises(StructureNotPending):
        asyncio.run(
            alloc.approve(
                _Ctx(uuid.uuid4()),  # type: ignore[arg-type]
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                seen_hash="a" * 64,
                statement_version="v1",
            )
        )


def test_an_agent_or_staff_l3_is_refused_by_p04_and_nothing_is_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.identity.api import Forbidden
    from abacus.modules.review import api as review_api

    pending = _row("pending_approval")
    writes: list[str] = []

    async def found(tenant: object, return_id: object) -> list[alloc.StructureRow]:
        return [pending]

    async def refuse(*args: object, **kwargs: object) -> object:
        raise Forbidden("sign_off.create", "role")

    async def draft_of(tenant: object, row: object) -> Draft:
        writes.append("read")
        return RIDGELINE

    monkeypatch.setattr(alloc, "versions", found)
    monkeypatch.setattr(review_api, "sign_target", refuse)
    monkeypatch.setattr(alloc, "_draft_of", draft_of)
    with pytest.raises(Forbidden):
        asyncio.run(
            alloc.approve(
                _Ctx(uuid.uuid4()),  # type: ignore[arg-type]
                return_id=uuid.uuid4(),
                engagement_id=uuid.uuid4(),
                seen_hash="a" * 64,
                statement_version="v1",
            )
        )
    assert writes == []  # refused before any version is written or a run is started


def test_the_preparer_is_the_drafter_or_the_person_who_adopted_the_proposal() -> None:
    person = uuid.uuid4()
    assert preparer_of(_row("pending_approval", actor=str(person)), None) == {person}
    adopter = uuid.uuid4()
    assert preparer_of(_row("pending_approval", by="agent", actor="proposal:x"), adopter) == {
        adopter
    }
    assert preparer_of(_row("pending_approval", by="agent"), None) == frozenset()


def test_the_rerun_groups_are_capital_and_k1s() -> None:
    from abacus.modules.tax.entity_run_plan import GROUPS

    assert alloc.RERUN_GROUPS == ("capital", "k1s")
    assert set(alloc.RERUN_GROUPS) <= set(GROUPS)
