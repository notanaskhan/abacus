"""Who is acting, in which firm, with which firm role (ADR-002, ADR-023). TASK-007 design §4.

Built from a validated membership on every request (`service.resolve_context`), never from token
claims or a client-supplied value alone.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class SystemContext:
    """The platform acting for a firm (ADR-023, TASK-010 design §1): a retrieval run, started by
    `on_behalf_of` through an authorised request. Holds the matrix role `system` and nothing else.
    Built only by `identity.service.system_context` (CTX-001)."""

    tenant: TenantContext
    on_behalf_of: UUID
    run_id: UUID

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.tenant_id


Actor = AuthContext | SystemContext
