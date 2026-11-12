"""DEC-4417 (TASK-7427): an owner's own decision cards held by a run step. Planning materiality
is raised by a person's proposal (`materiality.propose` is `agent: deny`); the engagement run's
step holds on that card, succeeds once a decision is in force, and fails closed before anyone
has proposed."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import run_waits
from abacus.modules.agents.api import HeldCard, register_decision_source
from abacus.modules.assurance import materiality

TENANT = TenantContext(uuid.uuid4(), "system", "test")
ENGAGEMENT = uuid.uuid4()


def test_assurance_holds_the_planning_materiality_kind() -> None:
    import importlib

    importlib.import_module("abacus.modules.assurance.api")  # registers at import
    assert run_waits.decision_source(materiality.PROPOSE_KIND) is materiality.held_card


def test_a_second_source_for_a_kind_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_waits, "_SOURCES", {})

    async def one(tenant: TenantContext, engagement: uuid.UUID) -> HeldCard:
        return HeldCard("none")

    async def two(tenant: TenantContext, engagement: uuid.UUID) -> HeldCard:
        return HeldCard("decided")

    register_decision_source("probe_kind", one)
    register_decision_source("probe_kind", one)  # the same source again: fine
    with pytest.raises(ValueError, match="already registered"):
        register_decision_source("probe_kind", two)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    item: uuid.UUID | None,
    awaiting: list[object],
    statuses: list[str],
) -> None:
    async def item_of(tenant: TenantContext, engagement: uuid.UUID) -> uuid.UUID | None:
        return item

    async def cards(tenant: TenantContext, work_item: uuid.UUID, kinds: object) -> list[object]:
        return awaiting

    async def versions(tenant: TenantContext, work_item: uuid.UUID) -> list[object]:
        return [SimpleNamespace(status=s) for s in statuses]

    stubs: dict[str, Callable[..., Awaitable[object]]] = {
        "assurance_item_id": item_of,
        "awaiting_cards": cards,
        "versions_of": versions,
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(materiality, name, stub)


async def test_an_awaiting_card_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    card = uuid.uuid4()
    _patch(monkeypatch, item=uuid.uuid4(), awaiting=[SimpleNamespace(card_id=card)], statuses=[])
    assert await materiality.held_card(TENANT, ENGAGEMENT) == HeldCard("awaiting", card)


@pytest.mark.parametrize("status", ["decided", "revised"])
async def test_a_decision_in_force_lets_the_step_succeed(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    _patch(monkeypatch, item=uuid.uuid4(), awaiting=[], statuses=["proposed", status])
    assert await materiality.held_card(TENANT, ENGAGEMENT) == HeldCard("decided")


@pytest.mark.parametrize(
    ("item", "statuses"), [(None, []), (uuid.uuid4(), []), (uuid.uuid4(), ["proposed"])]
)
async def test_nothing_proposed_fails_closed_with_the_owners_code(
    monkeypatch: pytest.MonkeyPatch, item: uuid.UUID | None, statuses: list[str]
) -> None:
    _patch(monkeypatch, item=item, awaiting=[], statuses=statuses)
    found = await materiality.held_card(TENANT, ENGAGEMENT)
    assert found == HeldCard("none", code="materiality_not_proposed")
