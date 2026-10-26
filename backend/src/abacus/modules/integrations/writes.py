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
from uuid import UUID

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
    """Whether `ctx` may run `capability` against the client's system: never, in v1."""
    await _refuse(ctx, capability, client_id, await _reason(ctx, capability, client_id))


async def execute_write(
    ctx: Actor,
    capability: str,
    client_id: UUID,
    *,
    approval_ref: UUID | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Run a declared write (ADR-150). Refused and audited every time in v1; no writer runs.
    `approval_ref` and `idempotency_key` are the shape later versions need; neither is stored."""
    del approval_ref, idempotency_key
    await authorise_write(ctx, capability, client_id)
