"""A-07-T22 (TASK-6206; A-07 F2; DEC-2806): the completion projector read model.

Row acceptance: "Northwind on Tue Oct 6, 2026 reads 12 complete, 1 not applicable and 5 open with
exactly five blockers, and a rebuild from events yields identical rows." Here over Northwind's EBP
checklist (18 items, from the firm's content) with each item's fact as of Oct 6 9:30 AM; the
projector is pure over its providers, so deriving twice is the rebuild.
"""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from abacus.modules.assurance import completion_projector as cp
from abacus.modules.assurance.completion_projector import (
    CompletionRow,
    ItemFact,
    derive,
    engagement_type_of,
    summarise,
)
from abacus.modules.methodology.api import AssuranceChecklistItem

pytestmark = pytest.mark.asyncio
REPORT_DATE = date(2026, 10, 9)
OPEN_ON_OCT_6 = {"subsequent_events", "rep_letter", "mgmt_approval", "tcwg_260", "eqr"}
MANUAL_NA = "legal_letter"
KEYS = (
    "subsequent_events", "rep_letter", "legal_letter", "going_concern", "sum", "findings",
    "review_notes", "sign_offs", "fs_final", "disclosure_checklist", "mgmt_approval",
    "tcwg_260", "sd_mw_265", "form5500_tie", "schedules", "certification", "filing", "eqr",
)  # fmt: skip


def _items() -> list[AssuranceChecklistItem]:
    return [
        AssuranceChecklistItem(
            key=k,
            text=k,
            gate_tag="G7" if k == "rep_letter" else None,
            depends_on_client=k in {"rep_letter", "mgmt_approval"},
            due_on_report_date=k in {"subsequent_events", "rep_letter"},
            derived=k != MANUAL_NA,
        )
        for k in KEYS
    ]


@pytest.fixture
def facts(monkeypatch: pytest.MonkeyPatch) -> None:
    def provider(key: str) -> cp.FactProvider:
        async def answer(_t: object, _w: uuid.UUID) -> ItemFact:
            return ItemFact("open" if key in OPEN_ON_OCT_6 else "done", key)

        return answer

    monkeypatch.setattr(cp, "_FACTS", {k: provider(k) for k in KEYS})


def _rows(projected: list[cp.ProjectedRow]) -> list[CompletionRow]:
    return [
        CompletionRow(
            uuid.uuid4(), r.item_key, r.position,
            "not_applicable" if r.item_key == MANUAL_NA else r.status,
            r.derived, r.evidence_text, r.link_target, r.gate_tag, r.depends_on_client, r.due_on,
        )
        for r in projected
    ]  # fmt: skip


async def test_ac_northwind_on_oct_6_reads_12_complete_1_na_and_5_open(facts: None) -> None:
    tenant: Any = SimpleNamespace()  # Any: a test double
    projected = await derive(tenant, uuid.uuid4(), _items(), REPORT_DATE)
    checklist = summarise(_rows(projected))
    assert (checklist.done, checklist.not_applicable, checklist.open) == (12, 1, 5)
    assert checklist.counted == 17  # "12 of 17": N/A excluded
    assert {b.item_key for b in checklist.blockers} == OPEN_ON_OCT_6
    tagged = [b.item_key for b in checklist.blockers if b.gate_tag]
    assert tagged == ["rep_letter"]  # only the rep letter is tagged (G7)
    assert sum(b.depends_on_client for b in checklist.blockers) == 2
    assert sum(b.due_on == REPORT_DATE for b in checklist.blockers) == 2


async def test_ac_a_rebuild_from_the_facts_yields_identical_rows(facts: None) -> None:
    tenant: Any = SimpleNamespace()  # Any: a test double
    wi = uuid.uuid4()
    first = await derive(tenant, wi, _items(), REPORT_DATE)
    again = await derive(tenant, wi, _items(), REPORT_DATE)
    assert first == again


async def test_an_item_without_a_provider_reads_not_yet_derived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cp, "_FACTS", {})
    rows = await derive(SimpleNamespace(), uuid.uuid4(), _items()[:1], REPORT_DATE)  # type: ignore[arg-type]  # a test double or a private name the test pins
    assert (rows[0].status, rows[0].evidence_text) == ("open", cp.NOT_DERIVED)


async def test_the_subscriber_is_inert_until_m16(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[object] = []

    async def store_items(*a: object, **_k: object) -> int:
        called.append(a)
        return 0

    monkeypatch.setattr(cp, "store_items", store_items)
    event: Any = SimpleNamespace(  # Any: a test double
        tenant_id=uuid.uuid4(), event_id=uuid.uuid4(), payload={"work_item_id": str(uuid.uuid4())}
    )
    assert cp.completion_dark.COMPLETION_LIVE is False
    await cp.on_completion_event(event)
    assert called == []


@pytest.mark.parametrize(
    ("assurance_type", "plan", "expected"),
    [
        ("audit", "single_employer", "ebp_audit"),
        ("audit", None, "fs_audit"),
        ("review", None, "review"),
    ],
)
def test_the_template_follows_the_engagement_type(
    assurance_type: str, plan: str | None, expected: str
) -> None:
    assert engagement_type_of(assurance_type, plan) == expected
