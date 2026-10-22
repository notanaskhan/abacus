"""Registration slots for client-access scopes and consents (F-03-T08; chapter 03 §2.4).

Owners register how to resolve a scope (engagements: work_item, intake; requests: request_item;
tax: k1_package; assurance: governance_room, component) and how to check a consent
(organisations). Both fail closed: an unresolved scope is denied, an unregistered consent is not
given.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import TenantContext


@dataclass(frozen=True)
class ScopeFacts:
    client_id: UUID
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None


ScopeResolver = Callable[[TenantContext, UUID], Awaitable[ScopeFacts | None]]
ConsentCheck = Callable[[TenantContext, UUID, str, datetime], Awaitable[bool]]
_SCOPES: dict[str, ScopeResolver] = {}
_CONSENTS: dict[str, ConsentCheck] = {}


def _same(a: Callable[..., object], b: Callable[..., object]) -> bool:
    """The same function, even from a module executed twice (a reloaded `api.py`)."""
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def register_scope_resolver(scope_kind: str, lookup: ScopeResolver) -> None:
    known = _SCOPES.get(scope_kind)
    if known is not None and not _same(known, lookup):
        raise ValueError(f"scope kind {scope_kind!r} is already registered")
    _SCOPES[scope_kind] = lookup


async def resolve_scope(
    tenant: TenantContext, scope_kind: str, scope_id: UUID
) -> ScopeFacts | None:
    """The scope's facts, or None (deny) when the kind is unregistered or the scope unknown."""
    lookup = _SCOPES.get(scope_kind)
    return None if lookup is None else await lookup(tenant, scope_id)


def register_consent_check(purpose: str, lookup: ConsentCheck) -> None:
    if purpose in _CONSENTS:
        raise ValueError(f"consent purpose {purpose!r} is already registered")
    _CONSENTS[purpose] = lookup


async def consent_given(
    tenant: TenantContext, entity_id: UUID, purpose: str, at: datetime
) -> bool:
    """Whether a consent covers the purpose; an unregistered purpose is never given."""
    lookup = _CONSENTS.get(purpose)
    return False if lookup is None else await lookup(tenant, entity_id, purpose, at)
