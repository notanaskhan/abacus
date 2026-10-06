"""Who is acting, in which firm, with which firm role (ADR-002, ADR-023). TASK-007 design §4.

Built from a validated membership on every request (`service.resolve_context`), never from token
claims or a client-supplied value alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.repository import FirmRole


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


Actor = AuthContext | SystemContext


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
