"""Tenant-scoped database access (ADR-014). PROTECTED. The only package that opens connections."""

from abacus.kernel.db.models import Base
from abacus.kernel.db.session import (
    ActorKind,
    TenantContext,
    configure_engine,
    configure_identity_engine,
    configure_relay_engine,
    dispose_engine,
    identity_engine,
    relay_engine,
    tenant_connection,
    tenant_session,
    transaction_context,
)

__all__ = [
    "ActorKind",
    "Base",
    "TenantContext",
    "configure_engine",
    "configure_identity_engine",
    "configure_relay_engine",
    "dispose_engine",
    "identity_engine",
    "relay_engine",
    "tenant_connection",
    "tenant_session",
    "transaction_context",
]
