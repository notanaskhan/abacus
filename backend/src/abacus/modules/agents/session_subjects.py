"""Session subjects (T-04-T37; T-04 §4.3; DEC-4316): the record a workbench session may be bound
to, and how its owner authorises it. Workbench may not import the owning module (ADR-008), so the
owner registers here at its api's import: `register_session_subject("tax_return", resolver)`. The
resolver authorises the person's read of the record and answers its engagement, or raises
NotFound (a wall, an unknown record, a portal principal)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext

SubjectResolver = Callable[[AuthContext, UUID], Awaitable[UUID]]
_SUBJECTS: dict[str, tuple[SubjectResolver, str]] = {}
KIND_PATTERN: Final = r"^[a-z_]{1,40}$"


def register_session_subject(kind: str, resolver: SubjectResolver, capability: str) -> None:
    """`kind`'s resolver and the capability its sessions run."""
    if kind in _SUBJECTS and _SUBJECTS[kind][0] is not resolver:
        raise ValueError(f"session subject {kind!r} is already registered")
    _SUBJECTS[kind] = (resolver, capability)


async def subject_engagement(ctx: AuthContext, kind: str, subject_id: UUID) -> tuple[UUID, str]:
    """The subject's engagement and capability after its owner authorised the person."""
    found = _SUBJECTS.get(kind)
    if found is None:
        raise NotFound("session_subject")
    resolver, capability = found
    return await resolver(ctx, subject_id), capability
