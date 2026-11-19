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
from collections.abc import Awaitable, Callable
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
]
# Audited as an index (references carry no text): keep the order, append only.
W1_REFUSALS: Final[tuple[W1Refusal, ...]] = (
    "attest_client_posting_refused",
    "write_capability_not_released",
    "write_capability_disabled",
    "posting_not_enabled",
    "write_grant_missing",
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


async def w1_ledger(ctx: Actor, client_entity_id: UUID) -> W1Ledger:
    """C-02-T18: what posting needs about the entity's ledger, read through the owners' APIs
    (adjustments may not import connections or organisations, ADR-008)."""
    from abacus.modules.connections.api import entity_connections
    from abacus.modules.organisations.api import client_of_entity, entity_name

    client = await client_of_entity(ctx.tenant, client_entity_id)
    if client is None:
        raise W1Refused(facts={"reason": "write_grant_missing"})
    found = await entity_connections(cast(Any, ctx), client_entity_id)  # Any: an AuthContext
    qbo = next(
        (
            c.id
            for c in found.connections
            if c.provider == "quickbooks_online" and c.status != "revoked"
        ),
        None,
    )
    return W1Ledger(client, qbo, await entity_name(ctx.tenant, client_entity_id) or "")


class W1Refused(DomainConflict):
    """A W1 write was refused by one of ADR-344's switches (`facts.reason`)."""

    code = "write_capability_refused"


async def execute_write[T](
    ctx: Actor,
    capability: str,
    client_id: UUID,
    *,
    approval_ref: UUID | None = None,
    idempotency_key: str | None = None,
    w1: W1Scope | None = None,
    perform: Callable[[], Awaitable[T]] | None = None,
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
            return await perform()
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
