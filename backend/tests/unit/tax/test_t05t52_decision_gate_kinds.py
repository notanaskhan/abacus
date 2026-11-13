"""T-05-T52 (TASK-7903; T-05 F10; SHL-11 g, TXP-00, TXP-10, HOME-02; DEC-4905, DEC-4906): the
entity return's decision and gate kinds, C16 kinds and topics.

Row acceptance: "Daniel's HOME-02 shows the §754 card with code facts, and only Daniel can decide
it." The card's options and facts are code's; the kind is reserved to the engagement partner.
"""

from __future__ import annotations

import asyncio
import importlib
import uuid
from datetime import date
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.tax import entity_decisions as ed
from abacus.modules.tax import entity_gates as eg

importlib.import_module("abacus.modules.tax.api")  # registers the kinds, as the app does


def test_ac_754_card_carries_code_facts() -> None:
    card = ed.card_for([date(2025, 6, 30)], Decimal("28595"), 2025)
    assert [o.key for o in card.options] == ["elect_now", "file_without", "against"]
    assert card.options[0].figures == {"step_up": "28595"}
    assert "28,595 §743(b) adjustment" in (card.options[0].detail or "")
    context = {c.key: c.value for c in card.context}
    assert context["transfer"] == "6/30/2025"
    assert context["difference"] == "28,595"


def test_ac_754_without_a_basis_owner_names_the_transfer_only() -> None:
    card = ed.card_for([date(2025, 6, 30)], None, 2025)
    assert card.options[0].figures == {}
    assert {c.key: c.value for c in card.context}["difference"] == "Computed with partner basis"


def test_ac_754_kind_is_reserved_to_the_engagement_partner() -> None:
    from abacus.modules.review.api import decision_kind

    kind = decision_kind(ed.SECTION_754)
    assert kind.reserved_role == "engagement_partner"
    assert kind.options is ed.section_754_options


def test_ac_gate_kinds_registered() -> None:
    from abacus.modules.review import slots

    for code in eg.GATE_KINDS:
        assert code in slots._GATE_KINDS  # pyright: ignore[reportPrivateUsage] -- the registry is the thing tested


def test_ac_gates_hold_for_every_entity_return(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = TenantContext(uuid.uuid4(), "system", "t")
    returns = [uuid.uuid4(), uuid.uuid4()]
    approved = {returns[0]: True, returns[1]: False}

    async def entity_returns(_t: object, _e: object) -> list[uuid.UUID]:
        return returns

    async def allocation(_t: object, r: uuid.UUID) -> bool:
        return approved[r]

    monkeypatch.setattr(eg, "entity_returns", entity_returns)
    monkeypatch.setattr(eg, "allocation_approved", allocation)
    gate = eg._every(eg.allocation_approved)  # pyright: ignore[reportPrivateUsage] -- the registry is the thing tested

    async def check() -> bool:
        return await gate(tenant, uuid.uuid4())

    assert not asyncio.run(check())
    approved[returns[1]] = True
    assert asyncio.run(check())


def test_ac_no_entity_return_meets_the_mapping_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    async def none(_t: object, _e: object) -> list[uuid.UUID]:
        return []

    monkeypatch.setattr(eg, "entity_returns", none)
    assert asyncio.run(
        eg.mapping_complete(TenantContext(uuid.uuid4(), "system", "t"), uuid.uuid4())
    )


def test_ac_badge_and_stale_topics() -> None:
    from abacus.kernel import realtime

    for event, _ in ed.TOPIC_EVENTS:
        found = realtime.invalidation_of(event)
        assert found is not None
        assert ("work_item", "work_item_id") in found.topic_fields


def test_ac_c16_kinds() -> None:
    from abacus.modules.notifications.catalogue import CATALOGUE
    from abacus.modules.notifications.kinds import kind_of

    assert CATALOGUE["workbook.fix_applied"].kind == "workbook_fix_applied"
    assert CATALOGUE["tax_memo.went_stale"].kind == "tax_memo_stale"
    assert kind_of("tax_memo_stale") is not None
