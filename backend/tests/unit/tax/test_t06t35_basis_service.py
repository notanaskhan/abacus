"""T-06-T35 (TASK-8833; T-06 F3; TXP-08; DEC-5835): basis and section 754.

Row acceptance: "Only Owen Calder sees the request in the portal, a second send answers 409
decision_already_sent, and the agent cannot send or decide."
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.client_approvals import DECIDER_RULES
from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import basis_service as bs


def _request(contact_user: uuid.UUID) -> bs._Request:
    return bs._Request(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), None, contact_user,
        uuid.uuid4(), datetime.now(UTC), None, None,
    )  # fmt: skip


def test_ac_only_the_named_contact_sees_it() -> None:
    owen = uuid.uuid4()
    r = _request(owen)
    tenant = uuid.uuid4()
    assert bs._viewer_is_contact(TenantContext(tenant, "human", str(owen)), r)
    other = TenantContext(tenant, "human", str(uuid.uuid4()))
    assert not bs._viewer_is_contact(other, r)


def test_owner_grant_decides() -> None:
    assert DECIDER_RULES["section_754"].any_of == frozenset({"owner"})


def test_ac_agent_cannot_send() -> None:
    agent = SimpleNamespace(
        client=False, is_support=False, tenant=TenantContext(uuid.uuid4(), "agent", "run:1")
    )
    with pytest.raises(Forbidden):
        asyncio.run(bs.send_to_client(agent, uuid.uuid4(), contact_id=uuid.uuid4()))  # type: ignore[arg-type] -- an agent double


def test_ac_second_send_is_decision_already_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.organisations import api as orgs
    from abacus.modules.review import api as review_api
    from abacus.modules.tax.entity_depth_errors import DecisionAlreadySent

    return_id = uuid.uuid4()

    async def subject(*_a: object) -> tuple[str, uuid.UUID]:
        return "basis_adjustment_election", return_id

    async def undecided(*_a: object) -> None:
        return None

    async def loaded(*_a: object) -> tuple[uuid.UUID, object]:
        return uuid.uuid4(), object()

    async def authorise(*_a: object) -> None:
        return None

    async def portal(*_a: object) -> tuple[str, uuid.UUID, str]:
        return "active", uuid.uuid4(), "owen@example.test"

    class _S:
        async def __aenter__(self) -> _S:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

        async def execute(self, *_a: object) -> SimpleNamespace:
            return SimpleNamespace(first=lambda: SimpleNamespace(id=uuid.uuid4(), answered=None))

    monkeypatch.setattr(review_api, "card_subject", subject)
    monkeypatch.setattr(review_api, "card_decision", undecided)
    monkeypatch.setattr(orgs, "contact_portal_facts", portal)
    monkeypatch.setattr(bs, "_loaded", loaded)
    monkeypatch.setattr(bs, "authorise", authorise)
    monkeypatch.setattr(bs, "tenant_session", lambda _t: _S())
    person = SimpleNamespace(
        client=False, is_support=False, tenant=TenantContext(uuid.uuid4(), "human", "u"),
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
    )  # fmt: skip
    with pytest.raises(DecisionAlreadySent):
        asyncio.run(bs.send_to_client(person, uuid.uuid4(), contact_id=uuid.uuid4()))  # type: ignore[arg-type] -- a context double


def test_provider_registered() -> None:
    import abacus.modules.tax.api  # noqa: F401 -- registration at import
    from abacus.modules.engagements.api import client_approval_provider

    assert client_approval_provider("section_754") is bs.PROVIDER
