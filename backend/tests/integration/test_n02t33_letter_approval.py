"""N-02-T33 (TASK-2420; N-02 §3.11, §4.2; ENG-04; C7; C11; C13; DEC-1468) against Postgres:
letter approval, send and amend.

The row's acceptance: Daniel Reyes approves, a later fee edit voids the approval, and Send opens
a SIG-02 draft ordered Owen Calder then Daniel Reyes. Also: the approval is the partner's own on
the content hash and renders the draft final through C11; the database refuses an approval from
anyone else; G1 must come on or before the letter's date; C13 and C16 hear the request; C7's
events move the letter to Sent and Signed and lock the document; a signed letter takes an
addendum as its own C11 document.

Ridgeline's letter and template come from N-02-T32's suite (shared, not copied).
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import OutboxEvent
from abacus.modules.engagements import letter_flow, letters
from abacus.modules.engagements.letter_contract import FeeLineIn, LetterFeesIn
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.signatures import api as _signatures  # registers the letter source and sender

from .agent_tests.support import Seeder
from .test_n02t32_letter_composer import (  # the shared Ridgeline harness and its fixtures
    RIDGELINE_FEES,
    draft_of,
    engines,
    fresh_registry,
    ridgeline,
    seed,
)

__all__ = ["_signatures", "engines", "fresh_registry", "seed"]

pytestmark = pytest.mark.usefixtures("engines", "fresh_registry")


async def _approvable(
    seed: Seeder, *, decided: timedelta = timedelta(days=-1)
) -> tuple[AuthContext, uuid.UUID, uuid.UUID]:
    """Ridgeline drafted once, G1 decided (yesterday), Daniel independent, envelopes on."""
    ctx, engagement, template_version = await ridgeline(seed)
    await seed.open_engagement(
        ctx.tenant_id,
        engagement,
        decided_by=ctx.user_id,
        concluded=False,
        decided_at=datetime.now(UTC) + decided,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        ctx.tenant_id,
        engagement,
        ctx.user_id,
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'signatures.envelopes', 'true', 'n02t33', 'TASK-2420')",
        ctx.tenant_id,
    )
    await letters.draft_letter(ctx, engagement, draft_of(template_version), '"0"')
    return ctx, engagement, template_version


async def test_ac1_daniel_approves_a_fee_edit_voids_it_and_send_orders_owen_then_daniel(
    seed: Seeder,
) -> None:
    ctx, engagement, template_version = await _approvable(seed)

    requested = await letter_flow.request_approval(ctx, engagement, '"1"')
    assert requested.status == "draft"
    assert "letter.approve" in requested.allowed_actions

    approved = await letter_flow.approve_letter(ctx, engagement, '"1"')
    assert approved.status == "partner_approved"
    assert approved.approved_by_name == "Daniel Reyes"
    assert approved.approved_at is not None
    first = (
        await seed.rows(
            "SELECT id, content_hash, approval_content_hash, approved_by, "
            "final_document_version_id FROM engagement_letter_versions "
            "WHERE engagement_id = $1 AND version_no = 1",
            engagement,
        )
    )[0]
    assert first["approved_by"] == ctx.user_id
    assert first["approval_content_hash"] == first["content_hash"]
    final = (
        await seed.rows(
            "SELECT mode, content_hash, approval_ref FROM generated_document_versions "
            "WHERE id = $1",
            first["final_document_version_id"],
        )
    )[0]
    assert final["mode"] == "final"
    assert final["content_hash"] == first["content_hash"]

    # A later fee edit is a new Draft version; the approval stays, stale, on version 1.
    fees = LetterFeesIn.model_validate(
        {
            **RIDGELINE_FEES.model_dump(),
            "lines": [
                FeeLineIn(label="for the section 754 work", amount_cents=7_000_00),
                *RIDGELINE_FEES.lines[1:],
            ],
        }
    )
    edited = await letters.draft_letter(
        ctx, engagement, draft_of(template_version, fees=fees), '"1"'
    )
    assert edited.status == "draft"
    assert edited.approved_by_name is None and edited.approval_content_hash is None
    assert "letter.send" not in edited.allowed_actions
    stale = await seed.rows(
        "SELECT status, approved_by FROM engagement_letter_versions WHERE id = $1", first["id"]
    )
    assert (stale[0]["status"], stale[0]["approved_by"]) == ("superseded", ctx.user_id)
    with pytest.raises(letter_flow.LetterNotSendable):
        await letter_flow.send_letter(ctx, engagement)

    # Approved again, Send opens the C7 draft: Owen Calder, then Daniel Reyes countersigning.
    await letter_flow.approve_letter(ctx, engagement, '"2"')
    envelope = await letter_flow.send_letter(ctx, engagement)
    assert await letter_flow.send_letter(ctx, engagement) == envelope  # one envelope per version
    signers = await seed.rows(
        'SELECT s."order", s.routing_group, s.role, s.identity_method, '
        "coalesce(c.display_name, u.display_name) AS name FROM envelope_signers s "
        "LEFT JOIN contacts c ON c.id = s.contact_id LEFT JOIN users u ON u.id = s.user_id "
        'WHERE s.envelope_id = $1 ORDER BY s."order"',
        envelope,
    )
    assert [(r["name"], r["role"], r["routing_group"], r["identity_method"]) for r in signers] == [
        ("Owen Calder", "signer", 1, "email_code"),
        ("Daniel Reyes", "countersigner", 2, "firm_sso"),
    ]
    env = (
        await seed.rows(
            "SELECT status, purpose, source_kind, engagement_id, gate_kind FROM envelopes "
            "WHERE id = $1",
            envelope,
        )
    )[0]
    assert (env["status"], env["purpose"], env["source_kind"]) == (
        "draft",
        "engagement_letter",
        "engagement_letter",
    )
    assert (env["engagement_id"], env["gate_kind"]) == (engagement, "G3")
    with pytest.raises(letters.LetterLocked):  # the envelope carries the approved letter
        await letters.draft_letter(ctx, engagement, draft_of(template_version), '"3"')


async def test_ac1_only_the_partner_approves_and_the_database_holds_it(seed: Seeder) -> None:
    ctx, engagement, _ = await _approvable(seed)
    agent = replace(
        ctx, tenant=TenantContext(ctx.tenant_id, "agent", f"agent:letters:{uuid.uuid4()}")
    )
    with pytest.raises(Forbidden):
        await letter_flow.approve_letter(agent, engagement, '"1"')
    with pytest.raises(letters.LetterStale):
        await letter_flow.approve_letter(ctx, engagement, '"0"')

    # The database: no transaction but the approver's own moves a version to partner_approved.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            ctx.tenant_id,
            ("system", "test"),
            "UPDATE engagement_letter_versions SET status = 'partner_approved', "
            "approved_by = $1, approved_at = now(), approval_content_hash = content_hash "
            "WHERE engagement_id = $2",
            ctx.user_id,
            engagement,
        )


async def test_ac1_g1_must_come_on_or_before_the_letter_date(seed: Seeder) -> None:
    ctx, engagement, _ = await _approvable(seed, decided=timedelta(days=3))
    with pytest.raises(DomainConflict) as refused:
        await letter_flow.approve_letter(ctx, engagement, '"1"')
    assert refused.value.code == "letter_before_acceptance"


async def test_ac1_the_request_waits_on_each_partner_and_clears_on_approval(
    seed: Seeder,
) -> None:
    ctx, engagement, _ = await _approvable(seed)
    await letter_flow.request_approval(ctx, engagement, '"1"')
    due = await letter_flow.letter_partner_approvals_due(ctx.tenant, engagement)
    assert [(g.assignee_user_id, g.role) for g in due] == [(ctx.user_id, "engagement_partner")]
    events = await seed.rows(
        "SELECT payload FROM outbox_events WHERE tenant_id = $1 "
        "AND event_type = 'letter.approval_requested'",
        ctx.tenant_id,
    )
    assert len(events) == 1
    await letter_flow.approve_letter(ctx, engagement, '"1"')
    assert await letter_flow.letter_partner_approvals_due(ctx.tenant, engagement) == []


async def test_ac1_c7_moves_the_letter_to_sent_then_signed_and_it_takes_an_addendum(
    seed: Seeder,
) -> None:
    ctx, engagement, _ = await _approvable(seed)
    await letter_flow.approve_letter(ctx, engagement, '"1"')
    envelope = await letter_flow.send_letter(ctx, engagement)

    def event(kind: str, **extra: object) -> OutboxEvent:
        return OutboxEvent(
            uuid.uuid4(), ctx.tenant_id, kind, {"envelope_id": str(envelope), **extra}
        )

    await letter_flow.on_envelope_event(event("envelope.send_approved"))
    assert (await letters.composed_letter(ctx, engagement)).status == "sent"
    completed = event("envelope.completed", source_kind="engagement_letter")
    await letter_flow.on_envelope_event(completed)
    await letter_flow.on_envelope_event(completed)  # redelivery is a no-op
    signed = await letters.composed_letter(ctx, engagement)
    assert signed.status == "signed"
    assert signed.allowed_actions == ["letter.read", "letter.amend"]
    locks = await seed.value(
        "SELECT count(*) FROM generated_document_events e JOIN engagement_letter_versions v "
        "ON v.generated_document_id = e.generated_document_id "
        "WHERE v.engagement_id = $1 AND e.kind = 'locked'",
        engagement,
    )
    assert locks == 1

    addendum = await letter_flow.amend_letter(ctx, engagement)
    assert (addendum.status, addendum.version) == ("draft", 2)
    rows = await seed.rows(
        "SELECT kind, amends_version_id, generated_document_id, status, version_no "
        "FROM engagement_letter_versions WHERE engagement_id = $1 ORDER BY version_no",
        engagement,
    )
    assert [(r["kind"], r["status"]) for r in rows] == [
        ("original", "signed"),
        ("addendum", "draft"),
    ]
    assert rows[1]["amends_version_id"] is not None
    assert rows[1]["generated_document_id"] != rows[0]["generated_document_id"]
    owner = cast(
        uuid.UUID,
        await seed.value(
            "SELECT owner_id FROM generated_documents WHERE id = $1",
            rows[1]["generated_document_id"],
        ),
    )
    assert owner == rows[1]["amends_version_id"]
