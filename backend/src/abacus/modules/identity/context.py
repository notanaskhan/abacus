"""Who is acting, in which firm, with which firm role (ADR-002, ADR-023). TASK-007 design §4.

Built from a validated membership on every request (`service.resolve_context`), never from token
claims or a client-supplied value alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.repository import FirmRole, active_memberships


@dataclass(frozen=True)
class AuthContext:
    tenant: TenantContext
    user_id: UUID
    membership_id: UUID
    firm_role: FirmRole | None
    mfa_at: datetime | None

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.tenant_id


# Only `identity.service` holds this: a SystemContext built anywhere else fails at construction.
_ISSUER = object()


@dataclass(frozen=True)
class SystemContext:
    """The platform acting for a firm on one run, on one engagement (ADR-023; TASK-010 design §1,
    revision 1). Holds the matrix role `system`, and `authorise` confines it to `engagement_id`.
    Built only by `identity.service.system_context_for_run`, which connections calls after
    proving the run from the database (SYS-001, CTX-001)."""

    tenant: TenantContext
    on_behalf_of: UUID
    run_id: UUID
    engagement_id: UUID
    issued_by: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.issued_by is not _ISSUER:
            raise TypeError("SystemContext is issued only by identity.service")
        if self.tenant.actor_kind != "system" or self.tenant.actor_id != f"run:{self.run_id}":
            raise ValueError("a system context acts as its run")

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.tenant_id


@dataclass(frozen=True)
class AgentContext:
    """An agent acting on one run, on one engagement, for one person (ADR-005, ADR-025; TASK-011
    design §1). `authorise` grants it an action only if the matrix's `agent` value allows it
    within `task_scope` AND `initiator` (the human whose action led here) is allowed it too.
    Built only by `identity.context.agent_context_for_run`, which the agents module calls after
    proving the run from the database (SYS-001)."""

    tenant: TenantContext
    agent_id: str
    agent_run_id: UUID
    engagement_id: UUID
    task_scope: frozenset[str]
    initiator: AuthContext
    issued_by: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.issued_by is not _ISSUER:
            raise TypeError("AgentContext is issued only by identity")
        if self.tenant.actor_kind != "agent" or self.tenant.actor_id != (
            f"agent:{self.agent_id}:{self.agent_run_id}"
        ):
            raise ValueError("an agent context acts as its run")
        if self.initiator.tenant_id != self.tenant.tenant_id:
            raise ValueError("an agent acts for someone in its own firm")

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.tenant_id


Actor = AuthContext | SystemContext | AgentContext


def system_context_for_run(
    *, tenant_id: UUID, run_id: UUID, engagement_id: UUID, on_behalf_of: UUID
) -> SystemContext:
    """The platform acting on one run. The caller (connections' run loader only, SYS-001) has
    read the run from the database under the tenant's row-level security and passes its
    recorded values: the run row is the proof, never a workflow's input."""
    return SystemContext(
        TenantContext(tenant_id, "system", f"run:{run_id}"),
        on_behalf_of,
        run_id,
        engagement_id,
        _ISSUER,
    )


class NoActiveTenant(Exception):
    """Authenticated, but no tenant this user may act in was chosen."""


async def agent_context_for_run(
    *,
    tenant_id: UUID,
    run_id: UUID,
    agent_id: str,
    engagement_id: UUID,
    task_scope: frozenset[str],
    initiator_user_id: UUID,
) -> AgentContext:
    """The agent acting on one run, for the agents module's run loader only (SYS-001), which has
    read the run under row-level security. The initiator's context (ADR-025) is resolved here from
    their active membership, read now, and never handed out: no other module can hold a person's
    context without their request. A revoked membership ends the agent's rights
    (`NoActiveTenant`)."""
    memberships = [
        m for m in await active_memberships(initiator_user_id) if m.tenant_id == tenant_id
    ]
    if len(memberships) != 1:
        raise NoActiveTenant("initiator has no active membership in this firm")
    membership = memberships[0]
    initiator = AuthContext(
        tenant=TenantContext(tenant_id, "human", str(initiator_user_id)),
        user_id=initiator_user_id,
        membership_id=membership.membership_id,
        firm_role=membership.firm_role,
        mfa_at=None,
    )
    return AgentContext(
        TenantContext(tenant_id, "agent", f"agent:{agent_id}:{run_id}"),
        agent_id,
        run_id,
        engagement_id,
        task_scope,
        initiator,
        _ISSUER,
    )
