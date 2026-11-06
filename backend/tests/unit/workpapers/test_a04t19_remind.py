"""A-04-T19's Remind (TASK-5019; A-04 §3.2 AC2.3; DEC-2388): "Remind… creates a follow-up draft to
Dana; the flag's history records each conversion." Nothing is sent, only a person drafts, and the
flag stays open. C5's drafting is P-06-T14's and has its own tests; here: what Remind asks it for.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from types import SimpleNamespace

import pytest

from abacus.kernel.db import ActorKind, TenantContext
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.workpapers import flags


def _ctx(kind: ActorKind = "human", *, client: bool = False) -> AuthContext:
    who = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), kind, str(who)),
        user_id=who,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=None,
        client=client,
    )


class _Tx:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.records: list[str] = []
        self.session = SimpleNamespace(add=self.added.append)

    def record(self, action: str, **_: object) -> None:
        self.records.append(action)

    async def __aenter__(self) -> _Tx:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _world(
    monkeypatch: pytest.MonkeyPatch, statuses: dict[str, str], drafted: int
) -> SimpleNamespace:
    items = [SimpleNamespace(id=uuid.uuid4(), status=s) for s in statuses.values()]
    ids = {k: i.id for k, i in zip(statuses, items, strict=True)}
    tx = _Tx()
    asked: list[object] = []
    flag = SimpleNamespace(id=uuid.uuid4(), state="open", work_item_id=uuid.uuid4())

    async def open_flag(*_: object) -> object:
        return flag

    async def request_items(*_: object) -> Sequence[object]:
        return items

    async def draft(
        _ctx: object, binders: list[uuid.UUID], chosen: list[uuid.UUID]
    ) -> list[object]:
        assert binders == []
        asked.extend(chosen)
        return [SimpleNamespace(id=uuid.uuid4()) for _ in range(drafted)]

    monkeypatch.setattr(flags, "_open_flag", open_flag)
    monkeypatch.setattr(flags, "request_items_for", request_items)
    monkeypatch.setattr(flags, "draft_follow_ups", draft)

    def uow(_tenant: object) -> _Tx:
        return tx

    monkeypatch.setattr(flags, "uow", uow)
    return SimpleNamespace(tx=tx, asked=asked, flag=flag, ids=ids)


async def test_ac2_3_remind_drafts_over_the_open_requests_and_keeps_the_flag_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _world(
        monkeypatch,
        {"a": "requested", "b": "returned", "c": "draft", "d": "accepted", "e": "uploaded"},
        drafted=2,
    )
    found = await flags.remind(_ctx(), uuid.uuid4(), uuid.uuid4(), world.flag.id)
    assert world.asked == [
        world.ids["a"],
        world.ids["b"],
    ]  # a draft request isn't the client's yet
    assert found.flag.state == "open"
    event = world.tx.added[0]
    assert event.event == "reminded"
    assert event.ref["to"] == "follow_up"
    assert len(event.ref["ids"]) == 2
    assert found.draft_id == uuid.UUID(event.ref["ids"][0])
    assert world.tx.records == ["attention_flag.reminded"]


async def test_nothing_to_chase_answers_409_and_records_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _world(monkeypatch, {"a": "accepted"}, drafted=0)
    with pytest.raises(flags.NothingToRemind):
        await flags.remind(_ctx(), uuid.uuid4(), uuid.uuid4(), world.flag.id)
    assert world.tx.added == []
    assert world.tx.records == []


@pytest.mark.parametrize(
    "ctx", [_ctx("agent"), _ctx("system"), _ctx(client=True)], ids=["agent", "system", "client"]
)
async def test_only_a_person_reminds(ctx: AuthContext, monkeypatch: pytest.MonkeyPatch) -> None:
    world = _world(monkeypatch, {"a": "requested"}, drafted=1)
    with pytest.raises(Forbidden):
        await flags.remind(ctx, uuid.uuid4(), uuid.uuid4(), world.flag.id)
    assert world.asked == []
