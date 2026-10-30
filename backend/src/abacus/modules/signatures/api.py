"""Public interface of the signatures module; other modules import only this (ADR-008).

C7 v1: the routers, and the slot sources register with (`sources.py`, N-02-T09). A source
(engagement letters, consents, e-file authorizations, rep letters, notices) registers providers
for an envelope's documents and signers, its gate, retention record type, checks and completed
label; it gets its summary from `envelope_summary_for` and its gate facts from
`envelope_gate_facts`. Record mode (N-02-T08) is frozen as C7 v1 (DEC-820).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.audit_owners import register_client_owners
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.uow import Handler, OutboxEvent
from abacus.modules.identity.api import AbacusRouter, AuthContext
from abacus.modules.signatures.activities import ACTIVITIES as ENVELOPE_ACTIVITIES
from abacus.modules.signatures.audit_targets import CLIENT_KINDS, audit_clients
from abacus.modules.signatures.contract import policies_router, portal_router, router
from abacus.modules.signatures.docusign_firm import firm_provider, register_docusign_install
from abacus.modules.signatures.events import EnvelopeSendApproved
from abacus.modules.signatures.hub import seal_ip
from abacus.modules.signatures.provider import (
    Completed,
    Created,
    EnvelopeSpec,
    EsignProvider,
    ProviderUnavailable,
    SignerEvidence,
    SignerState,
    configure_provider,
    register_firm_provider,
)
from abacus.modules.signatures.reminders import ReminderSender, register_reminder_sender
from abacus.modules.signatures.sources import (
    LETTER,
    LETTER_GATE,
    EnvelopeSource,
    UnknownEnvelopeSource,
    envelope_source,
    letter_envelope,
    letter_gate,
    register_envelope_source,
    register_letter_source,
    registered_sources,
)
from abacus.modules.signatures.status_poll import ACTIVITIES as STATUS_POLL_ACTIVITIES
from abacus.modules.signatures.status_poll import SCHEDULES as STATUS_POLL_SCHEDULES
from abacus.modules.signatures.status_poll import hint_envelope
from abacus.modules.signatures.workflows import (
    EnvelopeInput,
    EnvelopeStatusPollWorkflow,
    EnvelopeWorkflow,
    ReminderDue,
    SendPlan,
    envelope_workflow_id,
)


@dataclass(frozen=True)
class EnvelopeSummary:
    """What a source shows about its envelope: identifiers, the status code and counts."""

    envelope_id: UUID
    status: str
    signed: int
    total: int


@dataclass(frozen=True)
class GateFacts:
    """A gate's facts from envelopes (G3 letter signed; the e-file authorization)."""

    met: bool
    envelope_id: UUID | None
    completed_on: str | None


_NEWEST = text(
    "SELECT e.id, e.status, "
    "(SELECT count(*) FROM envelope_signers s WHERE s.envelope_id = e.id AND s.status = 'signed') "
    "AS signed, (SELECT count(*) FROM envelope_signers s WHERE s.envelope_id = e.id) AS total "
    "FROM envelopes e WHERE e.source_kind = :kind AND e.source_id = :source "
    "ORDER BY e.created_at DESC LIMIT 1"
)


async def envelope_summary_for(
    ctx: AuthContext, source_kind: str, source_id: UUID
) -> EnvelopeSummary | None:
    """The newest envelope for a source record, for a caller that authorised reading the source
    (identifiers, the status code and counts only)."""
    envelope_source(source_kind)
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(_NEWEST, {"kind": source_kind, "source": source_id})
        ).one_or_none()
    if row is None:
        return None
    return EnvelopeSummary(row.id, row.status, int(row.signed), int(row.total))


_COMPLETED_ON = text("SELECT completed_at::date FROM envelopes WHERE id = :id")


async def envelope_gate_facts(ctx: AuthContext, gate_kind: str, target_ref: UUID) -> GateFacts:
    """Gate facts for G3 (the engagement letter); other gates arrive with their sources."""
    if gate_kind != LETTER_GATE:
        return GateFacts(met=False, envelope_id=None, completed_on=None)
    envelope = await letter_envelope(ctx.tenant, target_ref)
    if envelope is None:
        fact = await letter_gate(ctx.tenant, target_ref)
        return GateFacts(met=fact.met, envelope_id=None, completed_on=None)
    async with tenant_session(ctx.tenant) as session:
        on = await session.scalar(_COMPLETED_ON, {"id": envelope})
    return GateFacts(met=True, envelope_id=envelope, completed_on=on.isoformat() if on else None)


register_letter_source()
# The trail places an envelope, and a consumed import file, on its client (SPEC-304; DEC-121).
register_client_owners(CLIENT_KINDS, audit_clients)

# N-02-T14: EnvelopeWorkflow on the time-sensitive queue; its activities by name.
WORKFLOWS: dict[type, WorkClass] = {
    EnvelopeWorkflow: "time_sensitive",
    EnvelopeStatusPollWorkflow: "background",  # N-02-T19: the 5-minute poll
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (*ENVELOPE_ACTIVITIES, *STATUS_POLL_ACTIVITIES)
SCHEDULES = STATUS_POLL_SCHEDULES
# N-02-T18: the provider for a firm with no process-wide one is its own DocuSign account, built
# only when the kill switch, W7 and a connected install allow (ProviderUnavailable otherwise).
register_firm_provider(firm_provider)


async def start_envelope(tenant_id: UUID, envelope_id: UUID) -> None:
    """Start the envelope's workflow once its send is committed (N-02-T22); a second start
    attaches to the running one."""
    await dispatch(
        EnvelopeWorkflow,
        EnvelopeInput(str(tenant_id), str(envelope_id)),
        id=envelope_workflow_id(str(tenant_id), str(envelope_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def on_send_approved(event: OutboxEvent) -> None:
    """N-02-T18: a send whose Undo window passed and whose grant the relay consumed."""
    await start_envelope(event.tenant_id, UUID(str(event.payload["envelope_id"])))


SUBSCRIPTIONS: dict[str, Handler] = {EnvelopeSendApproved.event_type: on_send_approved}


# The routers the API mounts, in order (P-39; F-03-T07). `/import` and `/summary` are declared
# before `/{envelope_id}` inside `router`.
ROUTERS: tuple[AbacusRouter, ...] = (router, policies_router, portal_router)

__all__ = [
    "ACTIVITIES",
    "LETTER",
    "ROUTERS",
    "SCHEDULES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "Completed",
    "Created",
    "EnvelopeInput",
    "EnvelopeSource",
    "EnvelopeSpec",
    "EnvelopeSummary",
    "EnvelopeWorkflow",
    "EsignProvider",
    "GateFacts",
    "ProviderUnavailable",
    "ReminderDue",
    "ReminderSender",
    "SendPlan",
    "SignerEvidence",
    "SignerState",
    "UnknownEnvelopeSource",
    "configure_provider",
    "envelope_gate_facts",
    "envelope_source",
    "envelope_summary_for",
    "envelope_workflow_id",
    "hint_envelope",
    "register_docusign_install",
    "register_envelope_source",
    "register_reminder_sender",
    "registered_sources",
    "seal_ip",
    "start_envelope",
]
