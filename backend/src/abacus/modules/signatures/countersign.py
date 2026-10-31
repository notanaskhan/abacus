"""Firm countersignature, a person's reminders and the envelope gates (N-02-T28; N-02 §3.7, §3.11,
§4.6; SIG-01, ENG-04; C13; INV-1; DEC-1479). RED.

- **Countersign session** (`POST /v1/envelopes/{id}/countersign/session`, `envelope.countersign`):
  only the firm signer the envelope names (a `user` signer with the `countersigner` role, e.g. the
  approving partner on a letter, N-02-T33) gets the provider's view, in the firm app on their staff
  SSO session with a fresh second factor. Any other person, partner or not, is refused 403 before
  anything is issued. The client's routing group signs first (the provider would refuse them too:
  409 `not_your_turn`); the envelope must be open at the provider and the provider switch on. The
  session reuses POR-06's one-time, five-minute session (its link read from the provider, never
  stored).
- **Reminders** (`envelope.remind`, a person; DEC-74): the preview counts who would get one
  (signers still to sign in each envelope's current routing group, under its policy's
  `max_reminders`) and sends nothing; the send uses the firm's published `signature_reminder`
  version the person previewed (409 `stale_version` when it changed), through `send_templated`,
  each keyed by the envelope, signer and sequence so a retry sends nothing twice. An envelope that
  is closed or at its cap is skipped and named.
- **C13 gate kinds**: `envelope_send` is met when no envelope on the engagement waits for its Send
  (none in `draft`); `envelope_countersign` when none waits on its firm countersignature (every
  client signer signed and a firm countersigner still pending). An envelope superseded or voided
  never holds a gate open.
- **HOME tiles**: `signatures_out` counts the viewer's visible envelopes out for signature
  (SIG-01's own count).
- **Activity**: the envelope's events take catalogue entries, so they read in the activity feeds.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import SIGNATURES_ENVELOPES, SIGNATURES_ESIGN_PROVIDER
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.audit_trail.api import CatalogueEntry
from abacus.modules.communications.api import (
    RecipientRef,
    SendScope,
    send_templated,
    template_version_in_use,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, firm_name
from abacus.modules.platform.api import HomeCount
from abacus.modules.signatures import hub, portal
from abacus.modules.signatures.activities import DEFAULT_CAP

COUNTERSIGN: Final = "envelope.countersign"
REMIND: Final = "envelope.remind"
REMINDER_KEY: Final = "signature_reminder"
SEND_GATE: Final = "envelope_send"
COUNTERSIGN_GATE: Final = "envelope_countersign"
_OPEN: Final = ("sent", "viewed", "partially_signed")


class TemplateStale(DomainConflict):
    """The `signature_reminder` version the person previewed is no longer the one in use."""

    code = "stale_version"


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("envelope")
    if ctx.is_support or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")  # INV-1: never the agent or the system


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)


# --- countersign -------------------------------------------------------------------------------

_FIRM_SIGNER = text(
    "SELECT e.id AS envelope_id, e.number, e.title, e.status, e.client_id, e.engagement_id, "
    "e.work_item_id, e.due_on, e.date_as_of, e.signer_order, e.provider, e.provider_envelope_id, "
    's.id AS signer_id, s."order", s.routing_group, s.status AS signer_status, s.viewed_at, '
    "s.user_id FROM envelopes e JOIN envelope_signers s ON s.envelope_id = e.id "
    "WHERE e.id = :id AND s.party_kind = 'user' AND s.role = 'countersigner' "
    'ORDER BY s."order" LIMIT 1'
)


async def countersign_session(ctx: AuthContext, envelope_id: UUID) -> portal.Session:
    """The named firm signer's provider view; anyone else 403 (N-02-T28's acceptance)."""
    _person(ctx, COUNTERSIGN)
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await hub.visible_head(ctx, session, envelope_id)
        row = (await session.execute(_FIRM_SIGNER, {"id": envelope_id})).mappings().first()
    await authorise(ctx, COUNTERSIGN, await hub.resource_of(ctx, head))
    if row is None or row["user_id"] != ctx.user_id:
        raise Forbidden(COUNTERSIGN, "attribute")  # only the firm signer the envelope names
    if ctx.mfa_at is None:
        raise portal.MfaRequired
    mine = portal.Mine(
        envelope_id=cast(UUID, row["envelope_id"]),
        number=int(cast(int, row["number"])),
        title=str(row["title"]),
        status=str(row["status"]),
        client_id=cast(UUID, row["client_id"]),
        engagement_id=cast(UUID | None, row["engagement_id"]),
        work_item_id=cast(UUID | None, row["work_item_id"]),
        due_on=cast(date | None, row["due_on"]),
        date_as_of=cast(date | None, row["date_as_of"]),
        signer_order=str(row["signer_order"]),
        provider=str(row["provider"]),
        provider_envelope_id=cast(str | None, row["provider_envelope_id"]),
        signer_id=cast(UUID, row["signer_id"]),
        order=int(cast(int, row["order"])),
        routing_group=int(cast(int, row["routing_group"])),
        signer_status=str(row["signer_status"]),
        viewed_at=None,
    )
    if mine.status not in _OPEN:
        raise portal.EnvelopeNotOpen(facts={"status": mine.status})
    if mine.signer_status == "signed":
        raise portal.EnvelopeNotOpen(facts={"status": "signed"})
    if mine.provider_envelope_id is None or mine.provider == "record":
        raise portal.EnvelopeNotOpen(facts={"status": "not_at_provider"})
    if await portal.earlier_unsigned(ctx, mine):
        raise portal.NotYourTurn
    if not await flag_enabled(ctx.tenant, SIGNATURES_ESIGN_PROVIDER):
        raise portal.ProviderUnavailable
    issued = await portal.issue_session(ctx, mine)
    return await portal.open_session(ctx, mine, issued)


# --- reminders ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RemindPlan:
    count: int
    skipped: tuple[UUID, ...]
    targets: tuple[tuple[UUID, UUID, UUID, int], ...]  # envelope, signer, contact, sequence


_ENVELOPE = text(
    "SELECT id, status, policy_family, purpose, expires_at, engagement_id, title, due_on "
    "FROM envelopes WHERE id = :id"
)
_WAITING = text(
    "SELECT id, contact_id, routing_group FROM envelope_signers WHERE envelope_id = :id "
    "AND party_kind = 'contact' AND status IN ('pending', 'viewed')"
)
_SENT = text(
    "SELECT count(*) FROM envelope_events WHERE envelope_id = :id AND kind = 'envelope.reminded'"
)
_POLICY = text(
    "SELECT max_reminders FROM envelope_policies WHERE policy_family = :family "
    "AND (purpose = :purpose OR purpose IS NULL) ORDER BY purpose NULLS LAST LIMIT 1"
)


async def _plan(ctx: AuthContext, envelope_ids: Sequence[UUID]) -> RemindPlan:
    skipped: list[UUID] = []
    targets: list[tuple[UUID, UUID, UUID, int]] = []
    for envelope_id in dict.fromkeys(envelope_ids):
        async with tenant_session(ctx.tenant) as session:
            head = await hub.visible_head(ctx, session, envelope_id)
            env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
            waiting = (await session.execute(_WAITING, {"id": envelope_id})).all()
            sent = int((await session.execute(_SENT, {"id": envelope_id})).scalar_one())
            cap = await session.scalar(
                _POLICY, {"family": env.policy_family, "purpose": env.purpose}
            )
        await authorise(ctx, REMIND, await hub.resource_of(ctx, head))
        expired = env.expires_at is not None and system_now() >= env.expires_at
        group = min((int(w.routing_group) for w in waiting), default=None)
        if (
            env.status not in _OPEN
            or expired
            or group is None
            or sent >= int(cap if cap is not None else DEFAULT_CAP)
        ):
            skipped.append(envelope_id)
            continue
        targets += [
            (envelope_id, w.id, w.contact_id, sent + 1)
            for w in waiting
            if int(w.routing_group) == group and w.contact_id is not None
        ]
    return RemindPlan(len(targets), tuple(skipped), tuple(targets))


async def remind_preview(ctx: AuthContext, envelope_ids: Sequence[UUID]) -> RemindPlan:
    """Who would get a reminder now; nothing is sent."""
    _person(ctx, REMIND)
    await _gate(ctx)
    return await _plan(ctx, envelope_ids)


async def _version_ok(ctx: AuthContext, version_id: UUID | None, version: int | None) -> None:
    in_use = await template_version_in_use(ctx.tenant, REMINDER_KEY)
    if in_use is None:
        raise TemplateStale(facts={"template": REMINDER_KEY})
    if version_id is not None and version_id != in_use:
        raise TemplateStale(facts={"template": REMINDER_KEY})
    if version_id is None and version is None:
        raise TemplateStale(facts={"template": REMINDER_KEY})


async def remind_send(
    ctx: AuthContext,
    envelope_ids: Sequence[UUID],
    template_version_id: UUID | None,
    template_version: int | None,
    idempotency_key: str,
) -> RemindPlan:
    """A person's reminder from the previewed template version, one email per waiting signer."""
    _person(ctx, REMIND)
    await _gate(ctx)
    await _version_ok(ctx, template_version_id, template_version)
    plan = await _plan(ctx, envelope_ids)
    firm = await firm_name(ctx.tenant_id)
    portal_link = f"{settings().app_base_url.rstrip('/')}/portal"
    sent_by: dict[UUID, int] = {}
    for envelope_id, signer_id, contact_id, sequence in plan.targets:
        async with tenant_session(ctx.tenant) as session:
            env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
        if env.engagement_id is None:
            continue
        key = hashlib.sha256(
            f"{idempotency_key}:{envelope_id}:{signer_id}:{sequence}".encode()
        ).hexdigest()
        outcome = await send_templated(
            ctx,
            REMINDER_KEY,
            RecipientRef("contact", contact_id),
            {
                "client_first_name": "there",
                "firm_name": firm,
                "document_title": str(env.title),
                "due_date": env.due_on.isoformat() if env.due_on is not None else "",
                "portal_link": portal_link,
            },
            scope=SendScope(engagement_id=env.engagement_id),
            idempotency_key=key,
        )
        if outcome.status == "queued":
            sent_by[envelope_id] = sent_by.get(envelope_id, 0) + 1
    for envelope_id, signers in sent_by.items():
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, "
                    "source, occurred_at) VALUES (:t, :e, NULL, 'envelope.reminded', 'firm', :at)"
                ),
                {"t": ctx.tenant_id, "e": envelope_id, "at": system_now()},
            )
            tx.record(
                "envelope.reminded",
                target=Target("envelope", envelope_id),
                after=Ref(signers=signers),
            )
    return RemindPlan(sum(sent_by.values()), plan.skipped, plan.targets)


# --- C13 gate kinds and the HOME tile ----------------------------------------------------------


async def send_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`envelope_send`: no envelope on the engagement waits for a person's Send."""
    async with tenant_session(tenant) as session:
        waiting = await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM envelopes WHERE engagement_id = :e "
                "AND status = 'draft' AND superseded_at IS NULL)"
            ),
            {"e": engagement_id},
        )
    return not bool(waiting)


async def countersign_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`envelope_countersign`: no open envelope waits only on its firm countersigner."""
    async with tenant_session(tenant) as session:
        waiting = await session.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM envelopes e WHERE e.engagement_id = :e "
                "AND e.status IN ('sent', 'viewed', 'partially_signed') "
                "AND e.superseded_at IS NULL "
                "AND EXISTS (SELECT 1 FROM envelope_signers s WHERE s.envelope_id = e.id "
                "AND s.party_kind = 'user' AND s.role = 'countersigner' AND s.status <> 'signed') "
                "AND NOT EXISTS (SELECT 1 FROM envelope_signers c WHERE c.envelope_id = e.id "
                "AND c.party_kind = 'contact' AND c.status <> 'signed'))"
            ),
            {"e": engagement_id},
        )
    return not bool(waiting)


async def signatures_out(viewer: object, office_id: UUID | None) -> HomeCount:
    """HOME-01's Signatures out tile: SIG-01's own count of visible envelopes out (DEC-43)."""
    del office_id  # an envelope belongs to no office
    found = await hub.summary(cast(AuthContext, viewer))
    return HomeCount(total=found.out, target_filter="tab=out")


# --- the envelope's events in the activity feeds ----------------------------------------------

ACTIVITY_KINDS: Final[dict[str, CatalogueEntry]] = {
    "envelope.drafted": CatalogueEntry("change", "pl", ()),
    "envelope.draft_saved": CatalogueEntry("change", "pl", ()),
    "envelope.send_requested": CatalogueEntry("decision", "ok", ()),
    "envelope.send_undone": CatalogueEntry("decision", "no", ()),
    "envelope.provider_sent": CatalogueEntry("communication", "pl", ()),
    "envelope.reminded": CatalogueEntry("communication", "pl", ()),
    "envelope.reminder_skipped": CatalogueEntry("communication", "no", ()),
    "envelope.viewed": CatalogueEntry("access", "pl", ()),
    "envelope.declined": CatalogueEntry("decision", "no", ()),
    "envelope.decline_withdrawn": CatalogueEntry("decision", "pl", ()),
    "envelope.expired": CatalogueEntry("change", "no", ()),
    "envelope.voided": CatalogueEntry("change", "no", ()),
    "envelope.evidence_recorded": CatalogueEntry("change", "pl", ()),
    "signer.signing_session_issued": CatalogueEntry("sign_in", "pl", ()),
}

__all__ = [
    "ACTIVITY_KINDS",
    "COUNTERSIGN",
    "COUNTERSIGN_GATE",
    "REMIND",
    "SEND_GATE",
    "RemindPlan",
    "TemplateStale",
    "countersign_gate",
    "countersign_session",
    "remind_preview",
    "remind_send",
    "send_gate",
    "signatures_out",
]
