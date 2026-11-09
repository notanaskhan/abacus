"""R-02-T11 (TASK-6309; SPEC-646 AC-1 to AC-7; DEC-63, DEC-3009): C18's approvals service.

Row acceptance: "Dana's accept of AJE-1 reaches adjustments.api.apply_client_decision with her
grant and MFA time, a stale seen_hash answers 409 item_changed, and agent, system and firm
principals are refused."

The service is exercised with a recording provider in place of adjustments' (the database half,
`apply_client_decision`'s row, is in the integration suite at the end pass); the grant, scope,
designation and idempotency lookups are faked so each test proves the order of the checks.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow.idempotency import Stored
from abacus.modules.engagements import client_approvals as ca
from abacus.modules.engagements.api import (
    ApprovalFacts,
    ApprovalItem,
    ClientDecision,
    ClientDecisionContext,
    ItemChanged,
    NotDecider,
)
from abacus.modules.identity.api import AuthContext, Forbidden, ScopeFacts
from abacus.modules.portal import approvals as service

TENANT = uuid.uuid4()
DANA = uuid.uuid4()
DANA_CONTACT = uuid.uuid4()
GRANT = uuid.uuid4()
CLIENT = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
WORK_ITEM = uuid.uuid4()
AJE_1 = uuid.uuid4()
MFA_AT = datetime(2026, 9, 25, 15, 2, tzinfo=UTC)


def _person(*, kind: str = "human", client: bool = True, session: bool = True) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(TENANT, kind, str(DANA)),  # type: ignore[arg-type] -- a test double stands in
        user_id=DANA,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=MFA_AT,
        client=client,
        portal_session_id=uuid.uuid4() if session else None,
    )


@dataclass
class Recording:
    item_state: str = "waiting"
    decided: list[tuple[uuid.UUID, ClientDecision, ClientDecisionContext]] = field(
        default_factory=list[tuple[uuid.UUID, ClientDecision, ClientDecisionContext]]
    )

    def aje(self) -> ApprovalItem:
        return ApprovalItem(
            kind="proposed_entry",
            item_id=AJE_1,
            scope_kind="work_item",
            scope_id=WORK_ITEM,
            sent_to_client=True,
            title="AJE-1 · Accrued audit fee",
            state=self.item_state,  # type: ignore[arg-type] -- a test double stands in
            seen_hash="hash-v1",
        )

    async def items(self, tenant: TenantContext, scope_id: uuid.UUID) -> Sequence[ApprovalItem]:
        return [self.aje()] if scope_id == WORK_ITEM else []

    async def item(self, tenant: TenantContext, item_id: uuid.UUID) -> ApprovalItem | None:
        return self.aje() if item_id == AJE_1 else None

    async def decide(
        self,
        tx: object,
        item_id: uuid.UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem:
        self.decided.append((item_id, decision, context))
        self.item_state = "accepted"
        return self.aje()

    async def facts(self, tenant: TenantContext, item_id: uuid.UUID) -> ApprovalFacts:
        return ApprovalFacts(False, WORK_ITEM)


class _Tx:
    def emit(self, _: object) -> None: ...

    def record(self, *_: object, **__: object) -> None: ...


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[Recording]:
    found = Recording()
    monkeypatch.setattr(ca, "_PROVIDERS", {"proposed_entry": found})
    yield found


@dataclass
class World:
    decider: bool = True
    covered: bool = True


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, provider: Recording) -> World:
    w = World()

    async def scope_facts(_: TenantContext, kind: str, scope_id: uuid.UUID) -> ScopeFacts | None:
        return ScopeFacts(CLIENT, ENGAGEMENT, WORK_ITEM)

    async def covering(*_: object, **__: object) -> uuid.UUID | None:
        return GRANT if w.covered else None

    async def decider(*_: object) -> ca.Decider | None:
        return ca.Decider("owner", GRANT, DANA_CONTACT) if w.decider else None

    async def attest(*_: object) -> bool:
        return False

    @asynccontextmanager
    async def uow(_: TenantContext) -> AsyncGenerator[_Tx]:
        yield _Tx()

    async def idempotent(
        _: TenantContext,
        *,
        route: str,
        key: str | None,
        body: object,
        run: Callable[[], Awaitable[tuple[int, dict[str, object]]]],
    ) -> Stored:
        status, out = await run()
        return Stored(status, out, replayed=False)

    @dataclass
    class _Grant:
        scope_id: uuid.UUID
        scope_kind: str = "work_item"

    async def grants(*_: object) -> list[_Grant]:
        # Dana's portal grant names the work item; a person outside the scope holds none.
        return [_Grant(WORK_ITEM)] if w.covered else []

    monkeypatch.setattr(service, "active_grants", grants)
    monkeypatch.setattr(service, "scope_facts", scope_facts)
    monkeypatch.setattr(service, "covering_grant", covering)
    monkeypatch.setattr(service, "decider_for", decider)
    monkeypatch.setattr(service, "attest_client_of", attest)
    monkeypatch.setattr(service, "uow", uow)
    monkeypatch.setattr(service, "idempotent", idempotent)
    return w


def _accept(seen: str = "hash-v1") -> ClientDecision:
    return ClientDecision("accept", seen)


async def test_ac_danas_accept_reaches_the_provider_with_her_grant_and_mfa_time(
    world: World, provider: Recording
) -> None:
    await service.client_decide(
        _person(), "proposed_entry", AJE_1, _accept(),
        action="proposed_entry.client_decide", idempotency_key="key-aje-1",
    )  # fmt: skip
    (item_id, decision, context) = provider.decided[0]
    assert item_id == AJE_1 and decision.decision == "accept"
    assert (context.grant_id, context.mfa_verified_at) == (GRANT, MFA_AT)
    assert (context.contact_id, context.user_id) == (DANA_CONTACT, DANA)
    assert context.designation_basis == "owner" and context.channel == "portal"


async def test_ac_a_stale_seen_hash_is_409_item_changed_and_writes_nothing(
    world: World, provider: Recording
) -> None:
    with pytest.raises(ItemChanged):
        await service.client_decide(
            _person(), "proposed_entry", AJE_1, _accept("hash-v0"),
            action="proposed_entry.client_decide", idempotency_key="key",
        )  # fmt: skip
    assert provider.decided == []


@pytest.mark.parametrize(
    "who",
    [
        _person(kind="agent"),
        _person(kind="system"),
        _person(client=False),  # a firm person
        _person(session=False),  # a client user with no portal session
    ],
    ids=["agent", "system", "firm", "no_portal_session"],
)
async def test_ac_agent_system_and_firm_principals_are_refused(
    world: World, provider: Recording, who: AuthContext
) -> None:
    with pytest.raises(Forbidden):
        await service.client_decide(
            who, "proposed_entry", AJE_1, _accept(),
            action="proposed_entry.client_decide", idempotency_key="key",
        )  # fmt: skip
    assert provider.decided == []


async def test_in_scope_but_not_the_decider_is_403_not_decider(
    world: World, provider: Recording
) -> None:
    world.decider = False
    with pytest.raises(NotDecider):
        await service.client_decide(
            _person(), "proposed_entry", AJE_1, _accept(),
            action="proposed_entry.client_decide", idempotency_key="key",
        )  # fmt: skip


async def test_out_of_scope_is_404(world: World, provider: Recording) -> None:
    from abacus.kernel.errors import NotFound

    world.covered = False
    with pytest.raises(NotFound):
        await service.approval(_person(), "proposed_entry", AJE_1)
    listing = await service.approvals(_person(), None, None)
    assert listing.items == []


async def test_a_decided_item_cannot_be_decided_again(world: World, provider: Recording) -> None:
    provider.item_state = "accepted"
    with pytest.raises(ItemChanged):
        await service.client_decide(
            _person(), "proposed_entry", AJE_1, _accept(),
            action="proposed_entry.client_decide", idempotency_key="key",
        )  # fmt: skip


async def test_the_list_offers_the_decider_accept_and_decline(
    world: World, provider: Recording, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def grants(*_: object) -> list[object]:
        @dataclass
        class G:
            scope_id: uuid.UUID
            scope_kind: str = "work_item"

        return [G(WORK_ITEM)]

    monkeypatch.setattr(service, "active_grants", grants)
    listing = await service.approvals(_person(), None, None)
    assert [s.item.item_id for s in listing.items] == [AJE_1]
    assert listing.items[0].actions == ("accept", "decline", "ask")
    assert listing.counts["waiting"] == 1
    world.decider = False
    listing = await service.approvals(_person(), None, None)
    assert listing.items[0].actions == ("ask",)


def test_the_decider_rule_covers_a_work_item_grant_only_for_its_item() -> None:
    at = ca.ApprovalScope(CLIENT, ENGAGEMENT, WORK_ITEM)
    assert ca.scope_covered(ScopeFacts(CLIENT, None, WORK_ITEM), at)
    assert not ca.scope_covered(ScopeFacts(CLIENT, None, uuid.uuid4()), at)
    assert ca.scope_covered(ScopeFacts(CLIENT, ENGAGEMENT, None), at)
    assert ca.scope_covered(ScopeFacts(CLIENT, None, None), at)
    assert not ca.scope_covered(ScopeFacts(uuid.uuid4(), None, None), at)


async def test_a_client_grant_lists_the_items_on_its_engagements(
    world: World, provider: Recording, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DEC-3025: a grant on the client covers its engagements; each item is still judged by its
    covering grant, so the list is never wider than the decider rule."""

    @dataclass
    class ClientGrant:
        scope_id: uuid.UUID
        scope_kind: str = "client"

    async def grants(*_: object) -> list[ClientGrant]:
        return [ClientGrant(CLIENT)]

    async def engagements_of_client(_: TenantContext, client_id: uuid.UUID) -> list[uuid.UUID]:
        return [ENGAGEMENT] if client_id == CLIENT else []

    async def items(_: TenantContext, scope_id: uuid.UUID) -> list[ApprovalItem]:
        return [provider.aje()] if scope_id == ENGAGEMENT else []

    monkeypatch.setattr(service, "active_grants", grants)
    monkeypatch.setattr(service, "engagements_of_client", engagements_of_client)
    monkeypatch.setattr(provider, "items", items)
    listing = await service.approvals(_person(), None, None)
    assert [s.item.item_id for s in listing.items] == [AJE_1]
    world.covered = False
    assert (await service.approvals(_person(), None, None)).items == []
