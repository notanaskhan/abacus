"""A-07-T26 / R-02-T12 remainder (DEC-3026): the `tcwg` grant a governance send gives each
recipient. A signed-in member holds the room at once; a contact who has never signed in gets a
pending grant and an invitation; a room of another client is refused, never granted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import contact_access as ca
from abacus.modules.identity.invitations import InvitationInvalid
from abacus.modules.identity.slots import ScopeFacts

pytestmark = pytest.mark.asyncio

TENANT = TenantContext(uuid.uuid4(), "human", "ep")
CLIENT = uuid.uuid4()
OTHER_CLIENT = uuid.uuid4()
BODY = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
EP = uuid.uuid4()


@dataclass
class Calls:
    granted: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    pending: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    invited: list[str] = field(default_factory=list[str])
    body_client: uuid.UUID = CLIENT


class _Tx:
    session: object = None

    def emit(self, *_: object, **__: object) -> None:
        return None


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    c = Calls()

    async def scope_facts(_: TenantContext, kind: str, scope_id: uuid.UUID) -> ScopeFacts | None:
        assert (kind, scope_id) == ("governance_room", BODY)
        return ScopeFacts(c.body_client)

    async def grant(_tx: object, **kw: object) -> uuid.UUID:
        c.granted.append(kw)
        return uuid.uuid4()

    async def pending(_session: object, row: dict[str, object]) -> uuid.UUID:
        c.pending.append(row)
        return uuid.uuid4()

    async def event(*_: object, **__: object) -> None:
        return None

    async def invitation(_tx: object, **kw: object) -> uuid.UUID:
        c.invited.append(str(kw["email"]))
        return uuid.uuid4()

    monkeypatch.setattr(ca, "scope_facts", scope_facts)
    monkeypatch.setattr(ca, "grant_in_unit_of_work", grant)
    monkeypatch.setattr(ca, "insert_pending_grant", pending)
    monkeypatch.setattr(ca, "insert_grant_event", event)
    monkeypatch.setattr(ca, "create_release_invitation", invitation)
    return c


async def _give(user: uuid.UUID | None, email: str | None) -> ca.K1Access:
    return await ca.grant_tcwg_member(
        _Tx(),  # pyright: ignore[reportArgumentType] -- a unit-of-work stand-in
        TENANT,
        engagement_id=ENGAGEMENT,
        client_id=CLIENT,
        contact_id=uuid.uuid4(),
        user_id=user,
        email=email,
        governance_body_id=BODY,
        granted_by=EP,
    )


async def test_a_signed_in_member_holds_the_room_at_once(calls: Calls) -> None:
    given = await _give(uuid.uuid4(), None)
    assert given.invitation_id is None and given.grant_id is not None
    [row] = calls.granted
    assert (row["role"], row["scope_kind"], row["scope_id"]) == ("tcwg", "governance_room", BODY)
    assert row["granted_by"] == EP


async def test_a_contact_who_never_signed_in_is_invited_with_a_pending_grant(calls: Calls) -> None:
    given = await _give(None, "ben.ashby@northwind.example")
    assert given.invitation_id is not None
    assert calls.pending[0]["role"] == "tcwg" and calls.granted == []
    assert calls.invited == ["ben.ashby@northwind.example"]
    with pytest.raises(InvitationInvalid):
        await _give(None, None)


async def test_a_room_of_another_client_is_refused(calls: Calls) -> None:
    calls.body_client = OTHER_CLIENT
    with pytest.raises(ca.ScopeOutsideClient):
        await _give(uuid.uuid4(), None)
    assert calls.granted == [] and calls.pending == []
