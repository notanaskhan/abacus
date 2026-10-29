"""Which engagement (or client entity) owns the rows an audit event can point at (SPEC-304;
SPEC-002 AC-5; DEC-121).

Each module registers, from its `api.py`, the target types it owns and a lookup from ids to the
owning engagement, or to the owning client entity or client (whose engagements then decide). The
audit explorer reads this registry, so it depends on no module that owns data, and a module that is
not loaded simply has no kinds: its targets are hidden (fail closed).

Follow-up (DEC-121): an `engagement_id` on audit events makes the lookup exact and cheap, and
this registry goes away.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext

Owners = Callable[[TenantContext, str, Sequence[UUID]], Awaitable[dict[UUID, UUID]]]

_ENGAGEMENT: Final[dict[str, Owners]] = {}
_ENTITY: Final[dict[str, Owners]] = {}
_CLIENT: Final[dict[str, Owners]] = {}


def _register(into: dict[str, Owners], kinds: Iterable[str], owners: Owners) -> None:
    for kind in kinds:
        if kind in _ENGAGEMENT or kind in _ENTITY or kind in _CLIENT:
            if into.get(kind) is owners:
                continue
            raise RuntimeError(f"the audit target type {kind!r} already has an owner")
        into[kind] = owners


def register_engagement_owners(kinds: Iterable[str], owners: Owners) -> None:
    """`owners(tenant, kind, ids)`: for rows of `kind`, their id -> the owning engagement."""
    _register(_ENGAGEMENT, kinds, owners)


def register_entity_owners(kinds: Iterable[str], owners: Owners) -> None:
    """`owners(tenant, kind, ids)`: for rows of `kind`, their id -> the owning client entity."""
    _register(_ENTITY, kinds, owners)


def register_client_owners(kinds: Iterable[str], owners: Owners) -> None:
    """`owners(tenant, kind, ids)`: for rows of `kind`, their id -> the owning client (a row that
    belongs to a client before any engagement does: firm intake, an envelope)."""
    _register(_CLIENT, kinds, owners)


def engagement_owners() -> dict[str, Owners]:
    return dict(_ENGAGEMENT)


def entity_owners() -> dict[str, Owners]:
    return dict(_ENTITY)


def client_owners() -> dict[str, Owners]:
    return dict(_CLIENT)
