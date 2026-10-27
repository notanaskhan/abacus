"""What a notification's subject says now, for the notification drawer's read-time facts and its
Approvals tab (P-04-T26; C16; SPEC-013 AC-7; DEC-605).

A notification stores no text and no state: only its kind and its subject's type and id. At read
time the drawer asks the subject's owner two things: the identifier-only facts its row may show
(codes, counts and ids, never a value or free text), and whether the subject still waits on the
reader (a pending row is in Approvals). Owners register from their `api.py`; the notifications
module reads this registry, so it depends on no module that owns data (`audit_owners`'
precedent). Fail closed: an unregistered subject type has no facts and is never pending, and an
owner that raises answers the same.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext

Fact = str | int | bool | None


@dataclass(frozen=True)
class SubjectState:
    pending: bool = False
    facts: dict[str, Fact] = field(default_factory=dict[str, Fact])


# (tenant, the reader, the subject's id) -> what the owner says now; None: unknown or hidden.
StateOf = Callable[[TenantContext, UUID, UUID], Awaitable[SubjectState | None]]
_STATES: Final[dict[str, StateOf]] = {}
NONE: Final = SubjectState()


def register_subject_state(subject_type: str, state_of: StateOf) -> None:
    known = _STATES.get(subject_type)
    if known is not None and (known.__module__, known.__qualname__) != (
        state_of.__module__,
        state_of.__qualname__,
    ):
        raise RuntimeError(f"the subject type {subject_type!r} already has a state owner")
    _STATES[subject_type] = state_of


async def subject_state(
    tenant: TenantContext, user_id: UUID, subject_type: str, subject_id: UUID
) -> SubjectState:
    owner = _STATES.get(subject_type)
    if owner is None:
        return NONE
    try:
        found = await owner(tenant, user_id, subject_id)
    except Exception:
        return NONE  # fail closed: a row whose owner can't answer is shown without facts
    return found if found is not None else NONE
