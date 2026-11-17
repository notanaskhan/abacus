# ac-test-author: notanaskhan
"""A-09-T35 (TASK-8524; ADR-078 independent AC tests for AY's amber group-scoping code and the
POR-23 room; SPEC-658 F5, F6; A-09 §3).

Written from SPEC-658 and the AUD-34 and POR-23 handoffs, not from the services. Each test seeds
the violation the rule prevents:

- scoping goldens: 5% x 4,800,000 = 240,000 gives PM 180,000 and CT 12,000; 4% = 192,000 gives
  144,000 and 9,600; component PM defaults follow the firm table and are refused at or above the
  group PM; coverage counts a component only when its planned work is more than analytics;
- the POR-23 read model is an allowlist: no amount, no figure of the group, no consolidated TB;
  the client never reads Expected, Received, Reviewed or Late;
- a component auditor's scope carries no engagement, so the consolidated TB (an engagement-wide
  resource) never passes `scope_only` for it;
- the thread's share guard refuses another component's figure.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date
from decimal import Decimal
from typing import get_args

import pytest

from abacus.modules.assurance import component_room, component_scope
from abacus.modules.assurance.compute import group_scoping as calc

D = Decimal


@pytest.mark.parametrize(
    ("rate", "materiality", "pm", "ct"),
    [
        (D("5"), "240000.00", "180000.00", "12000.00"),
        (D("4"), "192000.00", "144000.00", "9600.00"),
    ],
)
def test_group_materiality_goldens(rate: Decimal, materiality: str, pm: str, ct: str) -> None:
    found = calc.thresholds(D("4800000") * rate / 100)
    assert (str(found.materiality), str(found.pm), str(found.ct)) == (materiality, pm, ct)


@pytest.mark.parametrize(
    ("share", "expected"),
    [(D("62"), "135000.00"), (D("30"), "108000.00"), (D("12"), "90000.00"), (D("4"), "72000.00")],
)
def test_component_pm_defaults_follow_the_firm_table(share: Decimal, expected: str) -> None:
    assert str(calc.default_component_pm(D("180000"), share)) == expected


@pytest.mark.parametrize("pm", [D("180000"), D("200000"), D("0")])
def test_a_component_pm_at_or_above_group_pm_is_refused(pm: Decimal) -> None:
    with pytest.raises(calc.ComponentPmTooHigh):
        calc.validate_component_pm(pm, D("180000"))


def test_coverage_counts_only_components_with_more_than_analytics() -> None:
    found = calc.coverage(
        {"a": D("30000000"), "b": D("15000000"), "c": D("5760000")},
        {"a": "full_scope", "b": "specific_procedures", "c": "analytical_only"},
        D("50760000"),
    )
    assert (found.covered, found.not_covered) == (D("45000000.00"), D("5760000.00"))
    assert found.covered_pct + found.not_covered_pct == 100


def test_the_room_read_model_is_an_allowlist() -> None:
    room = {f.name for f in dataclasses.fields(component_room.Room)}
    assert room == {
        "id", "group_name", "component_name", "firm_name", "acknowledged_on", "uploaded",
        "expected", "deliverables",
    }  # fmt: skip
    deliverable = {f.name for f in dataclasses.fields(component_room.RoomDeliverable)}
    assert deliverable == {"id", "title", "due_on", "word", "uploaded_on", "return_note"}
    for name in room | deliverable:
        assert not any(w in name for w in ("amount", "balance", "pm", "materiality", "tb"))


def test_the_client_never_reads_a_firm_status_word() -> None:
    words = set(get_args(component_room.ClientWord))
    assert words.isdisjoint({"expected", "received", "reviewed", "late"})
    today = date(2026, 10, 2)
    assert component_room.client_word("expected", date(2026, 10, 1), False, today) == "overdue"
    assert component_room.client_word("expected", date(2026, 10, 9), False, today) == "due"
    assert (
        component_room.client_word("reviewed", date(2026, 10, 1), False, today) == "you_uploaded"
    )
    assert component_room.client_word("expected", date(2026, 10, 1), True, today) == "returned"


async def test_a_component_scope_carries_no_engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    engagement, client, component = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def scalar(self, *_a: object) -> uuid.UUID:
            return engagement

    async def client_of(_tenant: object, _engagement: object) -> uuid.UUID:
        return client

    import abacus.modules.engagements.api as engagements_api

    def session(_tenant: object) -> _Session:
        return _Session()

    monkeypatch.setattr(component_scope, "tenant_session", session)
    monkeypatch.setattr(engagements_api, "client_of", client_of)
    facts = await component_scope.component_scope(object(), component)  # type: ignore[arg-type]  # a stand-in tenant
    assert facts is not None
    assert facts.engagement_id is None and facts.work_item_id == component
    assert facts.client_id == client


def test_the_thread_share_guard_refuses_another_components_figure() -> None:
    own, other = [135_000_00], [108_000_00]
    assert component_scope.foreign_figures("Your PM is 135,000.", own, other) == []
    assert component_scope.foreign_figures("Real Estate PM is 108,000.", own, other) == [
        108_000_00
    ]
