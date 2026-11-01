"""T-01-T37's open pieces (TASK-2539; DEC-1580) against Postgres.

- Grace Holloway (client service) publishes the Feld return; `return.delivered` emails the
  household's owner "Deliverable ready" as Grace, under her `deliverable.publish` (she holds no
  `message.send`), once per release.
- Communications takes a send's authority from `SEND_AUTHORITIES` only: the pair, nothing else.
- Create issue on a rejected ack: Grace enters acks but holds no `issue.create`, so TAX-12 does
  not offer it to her and the route refuses her before the return moves.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import cast

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications import template_send
from abacus.modules.communications.api import RecipientRef, SendOutcome, SendScope
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import delivery, filed_delivery

from . import test_t01t37_transmission_acks as t01t37
from . import test_t01t41_filed_return_delivery as t01t41
from .conftest import MigratedDatabase
from .test_t01t25_engine_export import call_as, engines, feld_return

__all__ = ["engines", "gate"]
gate = t01t37.gate  # T-01-T37's signature gate stand-in
_member = t01t37._member  # pyright: ignore[reportPrivateUsage] -- T-01-T37's staff member seed
_world = t01t37._world  # pyright: ignore[reportPrivateUsage] -- T-01-T37's world
_accepted = t01t41._accepted  # pyright: ignore[reportPrivateUsage] -- T-01-T41's accepted return
_client = t01t41._client  # pyright: ignore[reportPrivateUsage] -- T-01-T41's household person
_authorise_send = template_send._authorise_send  # pyright: ignore[reportPrivateUsage] -- the gate under test

Sent = tuple[AuthContext, str, RecipientRef, Mapping[str, str], SendScope, str, str | None]


async def test_ac_a_published_return_emails_the_household_owner_once_as_grace(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    feld = await feld_return(migrated_db)
    await feld.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.delivery_efile', 'true', 't01-t37', 'T-01-T37')",
        feld.tenant,
    )
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    claire = await _client(feld, cast(uuid.UUID, feld.engagement))
    await _accepted(feld, grace)
    sent: list[Sent] = []

    async def stand_in(
        ctx: AuthContext,
        key: str,
        recipient: RecipientRef,
        variables: Mapping[str, str],
        *,
        scope: SendScope,
        idempotency_key: str,
        authority: str | None = None,
    ) -> SendOutcome:
        sent.append((ctx, key, recipient, variables, scope, idempotency_key, authority))
        return SendOutcome(uuid.uuid4(), "queued", None)

    monkeypatch.setattr(filed_delivery, "send_templated", stand_in)
    published = await filed_delivery.publish(grace, feld.item)
    payload = json.loads(
        cast(
            str,
            await feld.seed.value(
                "SELECT payload::text FROM outbox WHERE event_type = 'return.delivered' "
                "AND payload ->> 'return_id' = $1",
                str(feld.item),
            ),
        ),
    )
    event = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=feld.tenant,
        event_type="return.delivered",
        payload=payload,
    )
    await filed_delivery.on_delivered(event)
    ((ctx, key, recipient, variables, scope, idem, authority),) = sent
    assert (ctx.user_id, key, authority) == (
        grace.user_id,
        "deliverable_ready",
        "deliverable.publish",
    )
    assert recipient == RecipientRef("user", claire.user_id)
    assert scope.engagement_id == feld.engagement
    assert idem == f"return_delivered:{published.id}"
    assert variables["deliverable_title"] == "2025 Form 1040"
    assert set(variables) == {"client_first_name", "firm_name", "deliverable_title", "portal_link"}


async def test_a_send_takes_its_authority_only_from_the_allowed_pair(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    grace = await _member(feld.seed, feld, "Grace Holloway", "client_service")
    ref = await get_ref(grace, cast(uuid.UUID, feld.engagement))
    with pytest.raises(Forbidden):
        await _authorise_send(grace, ref, "deliverable_ready", None)  # no message.send
    await _authorise_send(grace, ref, "deliverable_ready", "deliverable.publish")
    await _authorise_send(grace, ref, "deliverable_ready", "k1_package.resend")  # DEC-1583
    with pytest.raises(Forbidden):
        await _authorise_send(grace, ref, "reminder", "deliverable.publish")
    with pytest.raises(Forbidden):
        await _authorise_send(grace, ref, "deliverable_ready", "inbox.read")


async def test_create_issue_is_not_offered_to_client_service_and_refuses_her(
    migrated_db: MigratedDatabase, gate: t01t37.Gate
) -> None:
    world = await _world(migrated_db, gate)
    assert await t01t37._designate(world, world.daniel) == 200  # pyright: ignore[reportPrivateUsage] -- the T-01-T37 suite's own helper
    gate.envelope = world.envelope
    status, _ = await t01t37._transmit(world, world.daniel)  # pyright: ignore[reportPrivateUsage] -- the T-01-T37 suite's own helper
    assert status == 201
    await t01t37._report(world, "rejected")  # pyright: ignore[reportPrivateUsage] -- the T-01-T37 suite's own helper
    ack = cast(
        uuid.UUID,
        await world.feld.seed.value(
            "SELECT id FROM efile_acks WHERE return_id = $1 AND status = 'rejected'",
            world.feld.item,
        ),
    )
    for_grace = await delivery.delivery(world.grace, world.feld.item)
    assert "efile_ack.record" in for_grace.allowed_actions
    assert "issue.create" not in for_grace.allowed_actions
    for_samuel = await delivery.delivery(world.feld.samuel, world.feld.item)
    assert "issue.create" in for_samuel.allowed_actions
    refused = await call_as(world.grace)(
        "POST",
        f"/v1/tax-returns/{world.feld.item}/acks/{ack}/issue",
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert refused.status_code == 403
    assert await t01t37._status(world) == "rejected"  # pyright: ignore[reportPrivateUsage] -- the T-01-T37 suite's own helper
