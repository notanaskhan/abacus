"""S38 end pass (TASK-7426; DEC-4415): a proposal kind whose owner registered an adapter is
approved without an in-transaction writer, and applied by its owner after the decision commits."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.modules.agents import approved_writes, proposal_slots, proposals


@pytest.fixture
def adapter_kind(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[uuid.UUID]]:
    applied: list[uuid.UUID] = []

    async def adapter(tenant: TenantContext, proposal_id: uuid.UUID) -> None:
        applied.append(proposal_id)

    monkeypatch.setitem(proposal_slots._ADAPTERS, "s38_probe", adapter)  # pyright: ignore[reportPrivateUsage]  # the slot itself
    yield applied


async def test_an_adapter_kind_needs_no_change_set_applier(adapter_kind: list[uuid.UUID]) -> None:
    assert proposal_slots.has_proposal_adapter("s38_probe")
    appliers, applier = await proposals._appliers("s38_probe", [])  # pyright: ignore[reportPrivateUsage]  # the gate
    assert appliers == {} and applier is not None
    with pytest.raises(proposal_slots.OwnerMissing):
        await proposals._appliers("s38_unregistered", [])  # pyright: ignore[reportPrivateUsage]  # the gate


@pytest.mark.parametrize(
    ("event_type", "decision", "applied"),
    [
        ("proposal.decided", "approved", True),
        ("proposal.decided", "approved_with_edits", True),
        ("proposal.decided", "rejected", False),
        ("proposal.undone", "approved", False),
    ],
)
async def test_the_decided_subscriber_applies_an_approved_adapter_kind_once(
    monkeypatch: pytest.MonkeyPatch,
    adapter_kind: list[uuid.UUID],
    event_type: str,
    decision: str,
    applied: bool,
) -> None:
    proposal_id = uuid.uuid4()
    row = SimpleNamespace(kind="s38_probe", agent_run_id=None, decision=decision)

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def execute(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(first=lambda: row)

    def _session(_tenant: object) -> _Session:
        return _Session()

    monkeypatch.setattr(approved_writes, "tenant_session", _session)
    event = OutboxEvent(uuid.uuid4(), uuid.uuid4(), event_type, {"proposal_id": str(proposal_id)})
    await approved_writes.on_proposal_event(event)
    assert adapter_kind == ([proposal_id] if applied else [])


async def test_an_apply_refused_for_the_approver_ends_the_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.kernel.errors import DomainForbidden

    class _Refused(DomainForbidden):
        code = "level_not_permitted"

    async def refusing(tenant: TenantContext, proposal_id: uuid.UUID) -> None:
        raise _Refused

    monkeypatch.setitem(proposal_slots._ADAPTERS, "s38_refused", refusing)  # pyright: ignore[reportPrivateUsage]  # the slot itself
    row = SimpleNamespace(kind="s38_refused", agent_run_id=None, decision="approved")

    class _Session:
        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def execute(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(first=lambda: row)

    def _session(_tenant: object) -> _Session:
        return _Session()

    monkeypatch.setattr(approved_writes, "tenant_session", _session)
    event = OutboxEvent(
        uuid.uuid4(), uuid.uuid4(), "proposal.decided", {"proposal_id": str(uuid.uuid4())}
    )
    await approved_writes.on_proposal_event(event)  # no exception: the outbox does not retry
