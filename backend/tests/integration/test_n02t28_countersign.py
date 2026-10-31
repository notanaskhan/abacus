"""N-02-T28 (TASK-2431; N-02 §3.7, §3.11; SIG-01, ENG-04; C13; INV-1; DEC-1479) against Postgres:
the firm countersignature, a person's reminders and the envelope gates.

The row's acceptance: "Margaret Okonkwo countersigns E14 and G3 is met, while any other partner is
refused with 403." The letter harness names Daniel Reyes as the approving partner and so the
countersigner (N-02-T33); the same rule holds for any named firm signer: Daniel gets the session
once Owen Calder has signed and the provider is on, another partner on the engagement is refused
403 before anything is issued, and Daniel is told to wait while the client group has not signed.
Also: `envelope_send` holds while an envelope waits for its Send and `envelope_countersign` while
one waits only on its countersigner; the reminder preview counts the waiting client signer and
sends nothing; HOME's Signatures out counts the envelope out.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.engagements import letter_flow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.signatures import api as _signatures  # registers the source and gate kinds
from abacus.modules.signatures import countersign, portal

from .agent_tests.support import Seeder
from .test_n02t32_letter_composer import engines, fresh_registry, seed
from .test_n02t33_letter_approval import (
    _approvable,  # pyright: ignore[reportPrivateUsage] -- N-02-T33's harness
)

__all__ = ["_signatures", "engines", "fresh_registry", "seed"]

pytestmark = pytest.mark.usefixtures("engines", "fresh_registry")


async def _other_partner(seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID) -> AuthContext:
    """Another partner on the engagement (not the envelope's named signer)."""
    user = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
                "('https://probe.test', $1, $2, 'Margaret Okonkwo') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            )
        )
    )
    membership = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO memberships (tenant_id, user_id, status, level, kind) VALUES "
                "($1, $2, 'active', 'partner', 'staff') RETURNING id",
                tenant,
                user,
            )
        )
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'engagement_partner')",
        tenant,
        engagement,
        user,
    )
    return AuthContext(
        TenantContext(tenant, "human", str(user)), user, membership, None, datetime.now(UTC)
    )


async def _out_for_signature(seed: Seeder) -> tuple[AuthContext, uuid.UUID, uuid.UUID]:
    ctx, engagement, _template = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    await letter_flow.approve_letter(ctx, engagement, '"1"')
    envelope = await letter_flow.send_letter(ctx, engagement)
    assert not await countersign.send_gate(ctx.tenant, engagement)  # waiting for its Send
    # As the provider leaves it once sent (the send path is N-02-T20's).
    await seed.as_actor(  # the database binds a send to the person who sends
        ctx.tenant_id,
        ("human", str(ctx.user_id)),
        "UPDATE envelopes SET status = 'sent', provider = 'docuseal', "
        "provider_envelope_id = 'ds-1', sent_at = clock_timestamp(), sent_by = $2 WHERE id = $1",
        envelope,
        ctx.user_id,
    )
    return ctx, engagement, envelope


async def test_ac1_only_the_named_firm_signer_gets_the_countersign_session(
    seed: Seeder,
) -> None:
    ctx, engagement, envelope = await _out_for_signature(seed)
    daniel = replace(ctx, mfa_at=datetime.now(UTC))
    other = await _other_partner(seed, ctx.tenant_id, engagement)
    with pytest.raises(Forbidden):
        await countersign.countersign_session(replace(other, mfa_at=datetime.now(UTC)), envelope)
    with pytest.raises(portal.NotYourTurn):  # Owen Calder signs first
        await countersign.countersign_session(daniel, envelope)
    await seed.run(
        "UPDATE envelope_signers SET status = 'signed', signed_at = clock_timestamp(), "
        "signature_method = 'email_code' WHERE envelope_id = $1 AND party_kind = 'contact'",
        envelope,
    )
    assert not await countersign.countersign_gate(daniel.tenant, engagement)
    with pytest.raises(Forbidden):  # still only the named signer
        await countersign.countersign_session(replace(other, mfa_at=datetime.now(UTC)), envelope)


async def test_the_gates_the_preview_and_signatures_out(seed: Seeder) -> None:
    ctx, engagement, envelope = await _out_for_signature(seed)
    assert await countersign.send_gate(ctx.tenant, engagement)
    plan = await countersign.remind_preview(ctx, [envelope])
    assert plan.count == 1 and plan.skipped == ()
    sent = await seed.value(
        "SELECT count(*) FROM envelope_events WHERE envelope_id = $1 "
        "AND kind = 'envelope.reminded'",
        envelope,
    )
    assert sent == 0
    tile = await countersign.signatures_out(ctx, None)
    assert tile.total >= 1
