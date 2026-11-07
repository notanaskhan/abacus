"""A-06-T16 seam (TASK-3395, DEC-2394): the `suggestion.created` subscriber mirrors only a pending
yes or no on a disclosure checklist item, and the applier writes adopted or edited answers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import AdoptedValue, PendingSuggestion
from abacus.modules.agents.proposal_slots import suggestion_applier
from abacus.modules.assurance import checklist_suggestions as seam
from abacus.modules.identity.api import AuthContext
from abacus.modules.reporting import statements

TENANT, DOCUMENT = uuid4(), uuid4()


def _event(target_type: str, suggestion: UUID) -> OutboxEvent:
    return OutboxEvent(
        event_id=uuid4(),
        tenant_id=TENANT,
        event_type="suggestion.created",
        payload={"suggestion_id": str(suggestion), "target_type": target_type},
    )


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    async def record(_tenant: TenantContext, *args: object) -> bool:
        calls.append(args)
        return True

    monkeypatch.setattr(seam, "record_suggested_answer", record)
    return calls


def _pending(
    value: dict[str, object], target_type: str = "disclosure_checklist"
) -> Callable[[TenantContext, UUID], Awaitable[PendingSuggestion]]:
    async def found(_tenant: TenantContext, suggestion_id: UUID) -> PendingSuggestion:
        return PendingSuggestion(suggestion_id, uuid4(), target_type, DOCUMENT, "a1.01", value)

    return found


async def test_ac_a_pending_yes_lands_on_its_item(
    monkeypatch: pytest.MonkeyPatch, recorded: list[tuple[Any, ...]]
) -> None:
    sid = uuid4()
    monkeypatch.setattr(seam, "pending_suggestion", _pending({"t": "text", "v": "yes"}))
    await seam.on_suggestion_created(_event("disclosure_checklist", sid))
    assert recorded == [(DOCUMENT, "a1.01", "yes", sid)]


@pytest.mark.parametrize(
    "value", [{"t": "text", "v": "na"}, {"t": "number", "v": "1"}, {"t": "text", "v": "maybe"}]
)
async def test_ac_na_and_anything_but_yes_or_no_are_not_mirrored(
    monkeypatch: pytest.MonkeyPatch, recorded: list[tuple[Any, ...]], value: dict[str, object]
) -> None:
    monkeypatch.setattr(seam, "pending_suggestion", _pending(value))
    await seam.on_suggestion_created(_event("disclosure_checklist", uuid4()))
    assert recorded == []


async def test_ac_another_targets_suggestion_and_a_decided_one_are_left_alone(
    monkeypatch: pytest.MonkeyPatch, recorded: list[tuple[Any, ...]]
) -> None:
    async def never(*_a: object) -> None:
        raise AssertionError("read for a target that isn't the checklist")

    monkeypatch.setattr(seam, "pending_suggestion", never)
    await seam.on_suggestion_created(_event("risk", uuid4()))

    async def decided(*_a: object) -> None:
        return None

    monkeypatch.setattr(seam, "pending_suggestion", decided)
    await seam.on_suggestion_created(_event("disclosure_checklist", uuid4()))
    assert recorded == []


async def test_ac_a_person_answering_meanwhile_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    async def conflict(*_a: object) -> bool:
        raise statements.StaleAnswer

    monkeypatch.setattr(seam, "pending_suggestion", _pending({"t": "text", "v": "no"}))
    monkeypatch.setattr(seam, "record_suggested_answer", conflict)
    await seam.on_suggestion_created(_event("disclosure_checklist", uuid4()))  # no raise
    assert issubclass(statements.StaleAnswer, DomainConflict)


@pytest.mark.parametrize(("cause", "edited"), [("suggestion_adopted", False), ("edit", True)])
async def test_ac_the_applier_is_registered_and_writes_adopted_or_edited(
    monkeypatch: pytest.MonkeyPatch, cause: str, edited: bool
) -> None:
    import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the applier

    assert suggestion_applier("disclosure_checklist") is seam.apply_checklist_suggestion
    seen: dict[str, object] = {}

    async def apply(_tx: object, _ctx: object, *args: object, **kwargs: object) -> None:
        seen.update(args=args, **kwargs)

    monkeypatch.setattr(seam, "apply_suggested_answer", apply)
    sid = uuid4()
    adopted = AdoptedValue(
        engagement_id=uuid4(),
        target_type="disclosure_checklist",
        target_id=DOCUMENT,
        field_key="a1.01",
        value={"t": "text", "v": "no"},
        value_source="human" if edited else "agent_suggested",
        cause=cause,  # pyright: ignore[reportArgumentType] -- one of the two causes
        suggestion_id=sid,
        citation_ids=(),
        citation_note=None,
        checkpoint_id=None,
        proposal_id=None,
    )
    user = uuid4()
    ctx = AuthContext(
        TenantContext(TENANT, "human", str(user)), user, uuid4(), None, datetime.now(UTC)
    )
    await seam.apply_checklist_suggestion(object(), ctx, adopted)  # pyright: ignore[reportArgumentType] -- the write is faked
    assert seen["args"] == (DOCUMENT, "a1.01", "no")
    assert (seen["suggestion_id"], seen["edited"]) == (sid, edited)
