"""What other modules do when someone joins an engagement's team (ADR-106). PROTECTED.

SPEC-025 (TASK-044): engagements asks the new member to confirm their independence, in the same
unit of work as the join. Identity calls the hook from every way a person joins (an added member,
the creator as partner, a self-joined firm administrator); it never imports engagements.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from abacus.kernel.uow import UnitOfWork

MemberAdded = Callable[[UnitOfWork, UUID, UUID], Awaitable[None]]
_member_added: MemberAdded | None = None


def register_member_added(handler: MemberAdded) -> None:
    global _member_added
    if _member_added is not None and _member_added is not handler:
        raise RuntimeError("the member-added handler is already registered")
    _member_added = handler


async def member_added(tx: UnitOfWork, engagement_id: UUID, user_id: UUID) -> None:
    """Inside the joining unit of work; nothing to do when no module registered."""
    if _member_added is not None:
        await _member_added(tx, engagement_id, user_id)
