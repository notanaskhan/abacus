"""Tenant-scoped database access (ADR-014). PROTECTED. The only package that opens connections."""

from abacus.kernel.db.session import (
    ActorKind,
    TenantContext,
    configure_engine,
    dispose_engine,
    tenant_session,
)

__all__ = ["ActorKind", "TenantContext", "configure_engine", "dispose_engine", "tenant_session"]
