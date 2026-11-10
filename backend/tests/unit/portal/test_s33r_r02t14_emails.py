"""R-02-T14 (DEC-3140; R-02 AC-36): the client's "approval requested" and "governance letter
sent" emails. One email per send and contact, in the sender's name; no sender, no email; a refusal
is logged and never raised."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import governance_comms
from abacus.modules.identity.api import Forbidden
from abacus.modules.portal import approval_emails

pytestmark = pytest.mark.asyncio
TENANT, CONTACT, SENDER, ENGAGEMENT, BATCH, WI = (uuid.uuid4() for _ in range(6))


def _event(**over: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "kind": "proposed_entry",
        "item_id": str(uuid.uuid4()),
        "scope_kind": "work_item",
        "scope_id": str(WI),
        "engagement_id": str(ENGAGEMENT),
        "recipient_contact_id": str(CONTACT),
        "sent_by": str(SENDER),
        "send_id": str(BATCH),
    }
    payload.update(over)
    return SimpleNamespace(tenant_id=TENANT, payload=payload)


@pytest.fixture
def sends(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    sent: list[dict[str, object]] = []

    async def member(_t: uuid.UUID, user: uuid.UUID) -> object:
        return SimpleNamespace(tenant=TenantContext(TENANT, "human", str(user)), user_id=user)

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[None]:
        yield None

    async def facts(_s: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, object]:
        return {i: SimpleNamespace(display_name="Dana Reyes", user_id=None) for i in ids}

    async def titles(_t: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return dict.fromkeys(ids, "FY2026 audit")

    async def firm(_t: uuid.UUID) -> str:
        return "Brightwater Hale"

    async def send(
        ctx: object, key: str, recipient: object, values: dict[str, str], **kw: object
    ) -> SimpleNamespace:
        sent.append({"ctx": ctx, "key": key, "recipient": recipient, "values": values, **kw})
        return SimpleNamespace(message_id=uuid.uuid4(), status="queued", blocked_reason=None)

    monkeypatch.setattr(approval_emails, "member_context", member)
    monkeypatch.setattr(approval_emails, "tenant_session", session)
    monkeypatch.setattr(approval_emails, "contact_facts", facts)
    monkeypatch.setattr(approval_emails, "work_item_titles", titles)
    monkeypatch.setattr(approval_emails, "firm_name", firm)
    monkeypatch.setattr(approval_emails, "send_templated", send)
    return sent


async def test_the_contact_gets_one_email_per_send_in_the_senders_name(
    sends: list[dict[str, object]],
) -> None:
    await approval_emails.on_approval_requested(_event())  # type: ignore[arg-type]  # a double
    (one,) = sends
    assert one["key"] == "approval_requested"
    assert one["idempotency_key"] == f"approval_requested:{BATCH}:{CONTACT}"
    assert one["values"] == {
        "client_first_name": "Dana",
        "firm_name": "Brightwater Hale",
        "work_item": "FY2026 audit",
        "portal_link": "http://localhost:5173/portal",
    }
    assert one["ctx"].user_id == SENDER  # type: ignore[attr-defined]  # a double


@pytest.mark.parametrize("missing", ["sent_by", "recipient_contact_id", "engagement_id"])
async def test_no_sender_or_recipient_no_email(
    sends: list[dict[str, object]], missing: str
) -> None:
    await approval_emails.on_approval_requested(_event(**{missing: None}))  # type: ignore[arg-type]  # a double
    assert sends == []


async def test_a_sender_who_left_sends_nothing(
    sends: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def gone(_t: uuid.UUID, _u: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(approval_emails, "member_context", gone)
    await approval_emails.on_approval_requested(_event())  # type: ignore[arg-type]  # a double
    assert sends == []


async def test_a_refusal_is_logged_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    async def member(_t: uuid.UUID, user: uuid.UUID) -> object:
        return SimpleNamespace(tenant=TenantContext(TENANT, "human", str(user)), user_id=user)

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[None]:
        yield None

    async def facts(_s: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, object]:
        return {i: SimpleNamespace(display_name="Dana", user_id=uuid.uuid4()) for i in ids}

    async def titles(_t: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {}

    async def firm(_t: uuid.UUID) -> str:
        return "Firm"

    async def refuse(*_a: object, **_k: object) -> None:
        raise Forbidden("message.send", "role")

    for name, fn in {
        "member_context": member,
        "tenant_session": session,
        "contact_facts": facts,
        "work_item_titles": titles,
        "firm_name": firm,
        "send_templated": refuse,
    }.items():
        monkeypatch.setattr(approval_emails, name, fn)
    await approval_emails.on_approval_requested(_event())  # type: ignore[arg-type]  # a double


async def test_the_governance_room_recipients_each_get_the_letter_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    async def titles(_t: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return dict.fromkeys(ids, "FY2026 audit")

    async def firm(_t: uuid.UUID) -> str:
        return "Firm"

    async def send(
        ctx: object, key: str, recipient: object, values: dict[str, str], **kw: object
    ) -> SimpleNamespace:
        sent.append({"key": key, "recipient": recipient, **kw})
        return SimpleNamespace(message_id=uuid.uuid4(), status="blocked", blocked_reason="x")

    monkeypatch.setattr(governance_comms, "work_item_titles", titles)
    monkeypatch.setattr(governance_comms, "firm_name", firm)
    monkeypatch.setattr(governance_comms, "send_templated", send)
    user, other, send_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    people = {
        CONTACT: SimpleNamespace(display_name="Dana Reyes", user_id=user),
        other: SimpleNamespace(display_name="Lee", user_id=None),
    }
    ctx = SimpleNamespace(tenant=TenantContext(TENANT, "human", str(SENDER)), tenant_id=TENANT)
    await governance_comms._letter_emails(  # pyright: ignore[reportPrivateUsage]  # under test
        ctx,  # type: ignore[arg-type]  # a double
        ENGAGEMENT,
        WI,
        send_id,
        [CONTACT, other],
        people,  # type: ignore[arg-type]  # doubles
    )
    assert [s["key"] for s in sent] == ["governance_letter_sent"] * 2
    assert {s["authority"] for s in sent} == {"governance_comm.approve_send"}
    assert sent[0]["recipient"].kind == "user" and sent[1]["recipient"].kind == "contact"  # type: ignore[attr-defined]  # doubles
    assert sent[1]["idempotency_key"] == f"governance_letter_sent:{send_id}:{other}"


def test_the_send_authority_is_registered() -> None:
    from abacus.modules.communications.template_registry import SEND_AUTHORITIES

    assert ("governance_letter_sent", "governance_comm.approve_send") in SEND_AUTHORITIES


def test_the_portal_subscribes_to_c18_requested() -> None:
    from abacus.modules.portal.api import SUBSCRIPTIONS

    assert SUBSCRIPTIONS["client_approval.requested"] is approval_emails.on_approval_requested
    assert "evidence.uploaded" in SUBSCRIPTIONS
