"""I-02-T11 (TASK-7720; I-02 F2; C1, C3; DEC-88; DEC-4723): the attention slot.

Fail-closed registration, an unregistered kind skipped and logged, DEC-88's both-sides rule on
dependents, and the C1 gates provider over the viewer's engagements only.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pytest

from abacus.modules.engagements import attention
from abacus.modules.engagements.attention import (
    AttentionRow,
    WorkItemHooks,
    attention_rows,
    dependents_visible,
    gates_blocking_requests,
    next_milestone,
    register_attention_provider,
    register_work_item_hooks,
)
from abacus.modules.engagements.gates import GateView


@dataclass(frozen=True)
class _Eng:
    id: uuid.UUID
    client_entity_name: str
    type: str = "audit"


CTX: Any = object()
FAIRHAVEN = _Eng(uuid.uuid4(), "Fairhaven")
NORTHWIND = _Eng(uuid.uuid4(), "Northwind")
WALLED = _Eng(uuid.uuid4(), "Walled")


@pytest.fixture
def visible(monkeypatch: pytest.MonkeyPatch) -> list[_Eng]:
    engs = [FAIRHAVEN, NORTHWIND]

    async def engagements_for(_ctx: object) -> Sequence[_Eng]:
        return engs

    import abacus.modules.engagements.service as service

    monkeypatch.setattr(service, "engagements_for", engagements_for)
    monkeypatch.setattr(attention, "_PROVIDERS", {})
    monkeypatch.setattr(attention, "_HOOKS", {})
    return engs


async def _rows(_ctx: object, engagements: Sequence[uuid.UUID]) -> list[AttentionRow]:
    return [AttentionRow("probe", e, "t", "d") for e in engagements]


async def _other(_ctx: object, _engagements: Sequence[uuid.UUID]) -> list[AttentionRow]:
    return []


def test_a_second_provider_for_a_kind_is_refused(visible: list[_Eng]) -> None:
    register_attention_provider("probe", _rows)
    register_attention_provider("probe", _rows)  # the same function again: idempotent
    with pytest.raises(ValueError, match="already registered"):
        register_attention_provider("probe", _other)


async def test_providers_see_only_the_viewers_engagements(visible: list[_Eng]) -> None:
    register_attention_provider("probe", _rows)
    rows = await attention_rows(CTX)
    assert {r.engagement_id for r in rows} == {FAIRHAVEN.id, NORTHWIND.id}
    assert WALLED.id not in {r.engagement_id for r in rows}


async def test_an_unregistered_kind_is_skipped_and_logged(
    visible: list[_Eng], monkeypatch: pytest.MonkeyPatch
) -> None:
    logged: list[str] = []

    class _Log:
        def warning(self, event: str, **_kw: object) -> None:
            logged.append(event)

    monkeypatch.setattr(attention, "_log", _Log())
    register_attention_provider("probe", _rows)
    rows = await attention_rows(CTX, ["nobody_registered", "probe"])
    assert {r.kind for r in rows} == {"probe"}
    assert logged == ["attention_kind_unregistered"]


async def test_dependents_need_both_engagements_open_dec_88(visible: list[_Eng]) -> None:
    feld, shah = uuid.uuid4(), uuid.uuid4()

    async def dependents(_ctx: object, _wi: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        return [(feld, NORTHWIND.id), (shah, WALLED.id)]

    async def milestone(_ctx: object, _wi: uuid.UUID) -> str | None:
        return "K-1 release"

    register_work_item_hooks("tax_return", WorkItemHooks(milestone, dependents))
    wi = uuid.uuid4()
    assert await next_milestone(CTX, "tax_return", wi) == "K-1 release"
    assert await dependents_visible(CTX, "tax_return", wi, FAIRHAVEN.id) == [feld]
    # The viewer cannot open the 1065's own engagement: nothing, either side.
    assert await dependents_visible(CTX, "tax_return", wi, WALLED.id) == []
    assert await next_milestone(CTX, "unknown_kind", wi) is None


async def test_unmet_c1_gate_blocks_requests(
    visible: list[_Eng], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def gates(_t: object, engagement_id: uuid.UUID, _type: str) -> list[GateView]:
        if engagement_id == FAIRHAVEN.id:
            return [GateView("G1", True, ()), GateView("G3", False, ("engagement_letter",))]
        return [GateView("G1", True, ()), GateView("G3", True, ())]

    import abacus.modules.engagements.gates as gates_module

    monkeypatch.setattr(gates_module, "engagement_gates", gates)

    class _Ctx:
        tenant: object = None

    rows = await gates_blocking_requests(_Ctx(), [FAIRHAVEN.id, NORTHWIND.id])  # type: ignore[arg-type]
    assert [(r.title, r.codes) for r in rows] == [
        ("Fairhaven · G3 not met", ("engagement_letter",))
    ]
