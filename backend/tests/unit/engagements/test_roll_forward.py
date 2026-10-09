"""SPEC-025 AC-2 (TASK-048): the roll-forward proposal rules, and creating exactly what was
confirmed."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref
from abacus.modules.engagements import roll_forward as rf
from abacus.modules.engagements.roll_forward import (
    PriorItem,
    RollForward,
    TeamMemberUnavailable,
    TemplateSeed,
    classify_items,
)
from abacus.modules.identity.api import AuthContext


def _item(description: str, status: str, area: str = "Cash") -> PriorItem:
    return PriorItem(uuid.uuid4(), description, area, "A", True, status)


def test_ac2_used_items_are_ticked_and_every_other_item_is_not() -> None:
    accepted = _item("Bank statements", "accepted")
    waived = _item("Petty cash count", "waived")
    open_ = _item("Loan agreements", "open")
    found = classify_items([accepted, waived, open_], [])
    assert [(p.kind, p.ticked) for p in found] == [
        ("used", True),
        ("not_used", False),
        ("not_used", False),
    ]
    assert found[0].prior_item_id == accepted.id
    assert found[0].client_visible and found[0].tier == "A"


def test_ac2_template_additions_are_flagged_and_ticked_matching_ignores_case_and_spacing() -> None:
    prior = [_item("Bank  statements", "accepted")]
    seeds = [
        TemplateSeed(0, "bank statements", "cash", "A"),  # last year's item: not new
        TemplateSeed(1, "Bank confirmations", "Cash", "B"),
    ]
    found = classify_items(prior, seeds)
    assert [(p.kind, p.description, p.ticked, p.template_key) for p in found] == [
        ("used", "Bank  statements", True, None),
        ("new_in_template", "Bank confirmations", True, 1),
    ]


def test_ac2_same_description_in_another_area_is_new() -> None:
    found = classify_items(
        [_item("Confirmations", "accepted", "Cash")],
        [TemplateSeed(0, "Confirmations", "Receivables", None)],
    )
    assert [p.kind for p in found] == ["used", "new_in_template"]


# --- creating ----------------------------------------------------------------------------------


class _Tx:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, object]]] = []

    def record(self, action: str, **kwargs: object) -> None:
        self.records.append((action, kwargs))


def _ctx() -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user_id)),
        user_id,
        uuid.uuid4(),
        "practice_leader",
        datetime.now(UTC),
    )


@dataclass
class Seen:
    added: list[tuple[uuid.UUID, str]] = field(default_factory=list[tuple[uuid.UUID, str]])
    copied: tuple[list[uuid.UUID], list[TemplateSeed]] | None = None
    gone: set[uuid.UUID] = field(default_factory=set[uuid.UUID])


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> Seen:
    seen = Seen()

    async def proposed(ctx: object, prior: uuid.UUID) -> list[PriorItem]:
        return []

    async def copy(
        tx: object,
        ctx: object,
        eng: uuid.UUID,
        prior: uuid.UUID,
        ids: list[uuid.UUID],
        seeds: list[TemplateSeed],
    ) -> int:
        seen.copied = (list(ids), list(seeds))
        return len(ids) + len(seeds)

    async def add(
        tx: object, ctx: object, eng: object, client: object, user: uuid.UUID, role: str
    ) -> None:
        if user in seen.gone:
            raise NotFound("person")
        seen.added.append((user, role))

    class _Ref:
        methodology_version_id = None

    async def get_ref(ctx: object, engagement_id: uuid.UUID) -> _Ref:
        return _Ref()

    monkeypatch.setattr(rf, "_items", (proposed, copy))
    monkeypatch.setattr(rf, "add_rolled_forward_member", add)
    monkeypatch.setattr(rf, "get_ref", get_ref)
    return seen


async def test_ac2_creating_adds_the_confirmed_team_but_not_the_creator(
    wired: Seen,
) -> None:
    ctx = _ctx()
    tx = _Tx()
    sam, alex = uuid.uuid4(), uuid.uuid4()
    roll = RollForward(
        uuid.uuid4(),
        [(sam, "senior"), (alex, "manager"), (ctx.user_id, "manager")],
        None,
        [uuid.uuid4()],
        [],
    )
    await rf.apply_roll_forward(tx, ctx, uuid.uuid4(), uuid.uuid4(), roll)  # pyright: ignore[reportArgumentType] -- a recording stand-in for the unit of work
    assert wired.added == [(sam, "senior"), (alex, "manager")]
    assert wired.copied == ([roll.prior_item_ids[0]], [])
    [(action, kwargs)] = tx.records
    assert action == "engagement.rolled_forward"
    after = kwargs["after"]
    assert isinstance(after, Ref) and after.fields["items_created"] == 1


async def test_ac2_someone_who_left_since_the_proposal_refuses_the_whole_creation(
    wired: Seen,
) -> None:
    ctx = _ctx()
    gone = uuid.uuid4()
    wired.gone.add(gone)
    roll = RollForward(uuid.uuid4(), [(gone, "staff")], None, [], [])
    with pytest.raises(TeamMemberUnavailable):
        await rf.apply_roll_forward(_Tx(), ctx, uuid.uuid4(), uuid.uuid4(), roll)  # pyright: ignore[reportArgumentType] -- a recording stand-in for the unit of work
    assert wired.copied is None


async def test_ac2_template_items_without_the_template_are_refused(wired: Seen) -> None:
    roll = RollForward(uuid.uuid4(), [], None, [], [3])
    with pytest.raises(DomainInvalid):
        await rf.apply_roll_forward(_Tx(), _ctx(), uuid.uuid4(), uuid.uuid4(), roll)  # pyright: ignore[reportArgumentType] -- a recording stand-in for the unit of work


def test_ac2_periods_are_dates() -> None:
    assert (
        rf.PriorChoice(uuid.uuid4(), "FY2025", date(2025, 1, 1), date(2025, 12, 31)).name
        == "FY2025"
    )
