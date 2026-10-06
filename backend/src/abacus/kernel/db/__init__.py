"""Tenant-scoped database access (ADR-014). PROTECTED. The only package that opens connections."""

from abacus.kernel.db.session import (
    ActorKind,
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
    relay_engine,
    tenant_connection,
    tenant_session,
)

__all__ = [
    "ActorKind",
    "TenantContext",
    "configure_engine",
    "configure_relay_engine",
    "dispose_engine",
    "relay_engine",
    "tenant_connection",
    "tenant_session",
]
