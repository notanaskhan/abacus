"""The write gate: `authorise_write` and `execute_write` (A-02-T15; ADR-150, P-17, DEC-46;
ADR-040; SPEC-333 AC-50; C20 v1).

Every write to a client's system would pass here, and in v1 every one is refused: the registry
enables nothing (`enabled` is false by type), no role holds `write_capability.execute` (the agent
included, I-AGENT-NEVER), and a W1-shaped capability is refused for an attest client at registry
level (I-POLICY-NOT-ATTEST). Each refusal is audited `write_capability.refused` on the client, in
its own unit of work (so it is kept although the call fails), with a fingerprint of the
capability key and the reason's index: references never carry text (ADR-031). Then
`WriteCapabilityRefused` (409 `write_capability_refused`) is raised. No `Writer` is ever looked
up or called.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import Actor, Forbidden, Resource, authorise
from abacus.modules.integrations.capabilities import (
    REASONS,
    RefusalReason,
    policy_refusal,
    write_capability,
)
from abacus.modules.organisations.api import attest_client_of

ACTION = "write_capability.execute"


class WriteCapabilityRefused(DomainConflict):
    """A write to a client's system was refused: the registry enables none (ADR-150)."""

    code = "write_capability_refused"

    def __init__(self, reason: RefusalReason) -> None:
        super().__init__(reason)
        self.reason = reason


def _fingerprint(capability: str) -> str:
    return hashlib.sha256(capability.encode()).hexdigest()


async def _reason(ctx: Actor, capability: str, client_id: UUID) -> RefusalReason:
    """The first rule that refuses; v1 always finds one. `authorise` runs every time, so the
    matrix's refusal (no role holds the action) is logged like any other denial."""
    entry = write_capability(capability)
    attest = await attest_client_of(ctx.tenant, client_id)
    try:
        await authorise(ctx, ACTION, Resource.client(ctx.tenant_id, client_id))
        permitted = True
    except Forbidden:
        permitted = False
    if entry is None:
        return "unknown_capability"
    if attest is None:
        return "unknown_client"
    refused = policy_refusal(entry, attest_client=attest)
    if refused is not None:
        return refused
    if not permitted:
        return "not_permitted"
    # Unreachable in v1: nothing is enabled. A later schema version replaces this module's
    # refusal with the ADR-150 path (dry run, approval, write-once evidence); until then, refuse.
    return "not_enabled"


async def _refuse(ctx: Actor, capability: str, client_id: UUID, reason: RefusalReason) -> None:
    async with uow(ctx.tenant) as tx:
        entry = write_capability(capability)
        fields: dict[str, str | int] = {
            "capability": _fingerprint(capability),
            "reason": REASONS.index(reason),
        }
        if entry is not None:
            fields["shape"] = int(entry.shape[1:])
        tx.record(
            "write_capability.refused", target=Target("client", client_id), after=Ref(**fields)
        )
    raise WriteCapabilityRefused(reason)


async def authorise_write(ctx: Actor, capability: str, client_id: UUID) -> None:
    """Whether `ctx` may run `capability` against the client's system: never, in v1. If working
    out why fails, the call is refused (`error`) and audited all the same (review L4)."""
    reason: RefusalReason = "error"
    try:
        reason = await _reason(ctx, capability, client_id)
    finally:
        await _refuse(ctx, capability, client_id, reason)


# --- W1: the five switches (C-02-T18; ADR-344 §3, §4; DEC-5704) ---------------------------------

W1_CAPABILITY: Final = "ledger_post_journal_entries"
W1Refusal = Literal[
    "attest_client_posting_refused",
    "write_capability_not_released",
    "write_capability_disabled",
    "posting_not_enabled",
    "write_grant_missing",
    "connection_needs_reauth",
]
# Audited as an index (references carry no text): keep the order, append only.
W1_REFUSALS: Final[tuple[W1Refusal, ...]] = (
    "attest_client_posting_refused",
    "write_capability_not_released",
    "write_capability_disabled",
    "posting_not_enabled",
    "write_grant_missing",
    "connection_needs_reauth",  # C-02-T20: appended
)


@dataclass(frozen=True)
class W1Scope:
    """Where a W1 write lands: the client, its entity, the connection and the engagement."""

    client_id: UUID
    client_entity_id: UUID
    connection_id: UUID
    engagement_id: UUID


_FIRM_SWITCH = text(
    "SELECT enabled FROM firm_write_capabilities WHERE capability_id = :cap "
    "ORDER BY changed_at DESC, id DESC LIMIT 1"
)
_ENGAGEMENT_SWITCH = text(
    "SELECT posting_enabled FROM connection_engagement_settings "
    "WHERE engagement_id = :e AND connection_id = :c"
)
_CLIENT_GRANT = text(
    "SELECT event FROM connection_write_grants WHERE connection_id = :c "
    "AND client_entity_id = :ce AND capability_id = :cap ORDER BY at DESC, id DESC LIMIT 1"
)

# The per-firm kill switch (`write.ledger.post_journal_entries`) answers through a reader C-02-T19
# registers; until then nothing is paused by it, and the registry switch keeps W1 dark.
KillSwitch = Callable[[TenantContext], Awaitable[bool]]
_kill_switch: list[KillSwitch] = []


def register_w1_kill_switch(reader: KillSwitch) -> None:
    _kill_switch[:] = [reader]


async def w1_refusal(tenant: TenantContext, scope: W1Scope) -> W1Refusal | None:
    """The first of ADR-344's switches that is off, checked in order: an attest client (never
    posted to), the registry entry (`enabled`), the firm's switch, the engagement's
    `posting_enabled`, the client owner's write grant, then the kill switch. None: all on."""
    attest = await attest_client_of(tenant, scope.client_id)
    if attest is None or attest:
        return "attest_client_posting_refused"
    entry = write_capability(W1_CAPABILITY)
    if entry is None or entry.shape != "W1" or not entry.enabled:
        return "write_capability_not_released"
    async with tenant_session(tenant) as session:
        firm = await session.scalar(_FIRM_SWITCH, {"cap": W1_CAPABILITY})
        engagement = await session.scalar(
            _ENGAGEMENT_SWITCH, {"e": scope.engagement_id, "c": scope.connection_id}
        )
        grant = await session.scalar(
            _CLIENT_GRANT,
            {"c": scope.connection_id, "ce": scope.client_entity_id, "cap": W1_CAPABILITY},
        )
    if firm is not True:
        return "write_capability_disabled"
    if engagement is not True:
        return "posting_not_enabled"
    if grant != "granted":
        return "write_grant_missing"
    if _kill_switch and await _kill_switch[0](tenant):
        return "write_capability_disabled"
    return None


@dataclass(frozen=True)
class W1Ledger:
    """The client entity's ledger for a W1 write: its client, its QuickBooks Online connection
    and its display name (CLS-07 c2's confirm line)."""

    client_id: UUID
    connection_id: UUID | None
    entity_name: str
    needs_reauth: bool = False  # C-02-T20: a connection needing reauth refuses posting everywhere


async def w1_ledger(ctx: Actor, client_entity_id: UUID) -> W1Ledger:
    """C-02-T18: what posting needs about the entity's ledger, read through the owners' APIs
    (adjustments may not import connections or organisations, ADR-008)."""
    from abacus.modules.connections.api import entity_connections
    from abacus.modules.organisations.api import client_of_entity, entity_name

    client = await client_of_entity(ctx.tenant, client_entity_id)
    if client is None:
        raise W1Refused(facts={"reason": "write_grant_missing"})
    found = await entity_connections(cast(Any, ctx), client_entity_id)  # Any: an AuthContext
    from abacus.modules.integrations.ledger_console import health_of

    qbo = next(
        (
            c
            for c in found.connections
            if c.provider == "quickbooks_online" and c.status != "revoked"
        ),
        None,
    )
    name = await entity_name(ctx.tenant, client_entity_id) or ""
    if qbo is None:
        return W1Ledger(client, None, name)
    reauth = health_of(qbo.status, qbo.status_reason) == "needs_reauth"
    return W1Ledger(client, qbo.id, name, reauth)


class W1Refused(DomainConflict):
    """A W1 write was refused by one of ADR-344's switches (`facts.reason`)."""

    code = "write_capability_refused"


# --- W1 evidence and the operation's trail (C-02-T19; ADR-344 §5; DEC-5705) ---------------------

EVIDENCE_YEARS: Final = 7  # the write-once bodies outlive the engagement's records (ADR-004)
WriteStatus = Literal["verified", "failed", "verify_mismatch"]


@dataclass(frozen=True)
class W1Evidence:
    """What one W1 call leaves behind: its request, the provider's response and the read-back,
    each stored write-once (Object Lock) with its SHA-256, and the operation's outcome."""

    response: bytes
    readback: bytes
    external_ref: str | None
    status: WriteStatus


@dataclass(frozen=True)
class W1Operation:
    """The write being made: what `ledger_write_operations` names (never a body)."""

    subject_type: str
    subject_id: UUID
    operation: Literal["create_journal_entry", "set_closing_date"]
    actor_user_id: UUID
    request: bytes


_OPERATION = text(
    "INSERT INTO ledger_write_operations (tenant_id, capability_id, client_entity_id, "
    "connection_id, subject_type, subject_id, operation, idempotency_key, approval_grant_id, "
    "actor_user_id) VALUES (:t, :cap, :ce, :c, :st, :sid, :op, :k, :g, :u) "
    "ON CONFLICT (tenant_id, capability_id, idempotency_key) DO NOTHING RETURNING id"
)
_OPERATION_AGAIN = text(
    "UPDATE ledger_write_operations SET attempt = attempt + 1, started_at = clock_timestamp() "
    "WHERE capability_id = :cap AND idempotency_key = :k RETURNING id"
)
_OPERATION_SENT = text(
    "UPDATE ledger_write_operations SET status = 'sent', started_at = clock_timestamp() "
    "WHERE id = :id"
)
_OPERATION_DONE = text(
    "UPDATE ledger_write_operations SET status = :s, external_ref = :ext, "
    "finished_at = clock_timestamp() WHERE id = :id"
)
_EVIDENCE = text(
    "INSERT INTO ledger_write_evidence (tenant_id, write_operation_id, kind, object_key, sha256, "
    "bytes) VALUES (:t, :op, :kind, :key, :sha, :n) "
    "ON CONFLICT (tenant_id, write_operation_id, kind) DO NOTHING"
)


async def _open_operation(
    ctx: Actor, scope: W1Scope, op: W1Operation, key: str, grant: UUID
) -> UUID:
    async with uow(ctx.tenant) as tx:
        found = await tx.session.scalar(
            _OPERATION,
            {"t": ctx.tenant_id, "cap": W1_CAPABILITY, "ce": scope.client_entity_id,
             "c": scope.connection_id, "st": op.subject_type, "sid": op.subject_id,
             "op": op.operation, "k": key, "g": grant, "u": op.actor_user_id},
        )  # fmt: skip
        if found is None:
            found = await tx.session.scalar(_OPERATION_AGAIN, {"cap": W1_CAPABILITY, "k": key})
        await tx.session.execute(_OPERATION_SENT, {"id": found})
        tx.record("ledger_write.sent", target=Target("ledger_write_operation", cast(UUID, found)))
    return cast(UUID, found)


async def _close_operation(ctx: Actor, op_id: UUID, request: bytes, out: W1Evidence) -> None:
    """The three bodies write-once under Object Lock (COMPLIANCE), then the outcome."""
    from datetime import timedelta

    from abacus.kernel.clock import system_now
    from abacus.modules.evidence.api import put_record

    until = system_now() + timedelta(days=365 * EVIDENCE_YEARS)
    stored = [
        (kind, await put_record(ctx.tenant_id, "ledger_write_evidence", body, until), len(body))
        for kind, body in (("request", request), ("response", out.response),
                           ("readback", out.readback))
    ]  # fmt: skip
    async with uow(ctx.tenant) as tx:
        for kind, record, size in stored:
            await tx.session.execute(
                _EVIDENCE,
                {"t": ctx.tenant_id, "op": op_id, "kind": kind, "key": record.key,
                 "sha": record.sha256, "n": size},
            )  # fmt: skip
        await tx.session.execute(
            _OPERATION_DONE, {"s": out.status, "ext": out.external_ref, "id": op_id}
        )
        tx.record(
            "ledger_write.verified" if out.status == "verified" else f"ledger_write.{out.status}",
            target=Target("ledger_write_operation", op_id),
        )


async def _ledger_write_paused(tenant: TenantContext) -> bool:
    from abacus.kernel.controls import control_active_now

    return await control_active_now("ledger_write_pause", tenant.tenant_id)


register_w1_kill_switch(_ledger_write_paused)


async def execute_write[T](
    ctx: Actor,
    capability: str,
    client_id: UUID,
    *,
    approval_ref: UUID | None = None,
    idempotency_key: str | None = None,
    w1: W1Scope | None = None,
    perform: Callable[[], Awaitable[T]] | None = None,
    operation: W1Operation | None = None,
    evidence_of: Callable[[T], W1Evidence] | None = None,
) -> T:
    """Run a declared write (ADR-150). Every capability but W1 is refused and audited, and no
    writer runs. W1 (ADR-344) runs `perform` only when the caller passes its scope, the consumed
    approval grant (`approval_ref`) and the idempotency key, and every switch is on at this call
    (the switches are re-read here, after the grant was consumed); otherwise it is refused and
    audited like any other write. Only `adjustments/posting.py` passes `w1` (POST-001)."""
    if (
        capability == W1_CAPABILITY
        and w1 is not None
        and perform is not None
        and approval_ref is not None
        and idempotency_key is not None
    ):
        refusal = await w1_refusal(ctx.tenant, w1)
        if refusal is None:
            if operation is None or evidence_of is None:
                return await perform()
            op_id = await _open_operation(ctx, w1, operation, idempotency_key, approval_ref)
            result = await perform()
            await _close_operation(ctx, op_id, operation.request, evidence_of(result))
            return result
        async with uow(ctx.tenant) as tx:
            tx.record(
                "write_capability.refused",
                target=Target("client", client_id),
                after=Ref(
                    capability=_fingerprint(capability), w1_reason=W1_REFUSALS.index(refusal)
                ),
            )
        raise W1Refused(facts={"reason": refusal})
    await authorise_write(ctx, capability, client_id)
    raise AssertionError("authorise_write always refuses")


AUDIT_ENTITY_KINDS: Final = frozenset({"ledger_write_operation"})
_OPERATION_ENTITIES = text(
    "SELECT id, client_entity_id FROM ledger_write_operations WHERE id = ANY(:i)"
)


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For W1 write operations named by an audit event: their id -> the client entity written to,
    so the trail applies that client's walls (C-02-T19)."""
    if kind not in AUDIT_ENTITY_KINDS or not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_OPERATION_ENTITIES, {"i": list(ids)})
        return {cast(UUID, r[0]): cast(UUID, r[1]) for r in rows}
