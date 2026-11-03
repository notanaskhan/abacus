"""A-05-T16 (DEC-2069): a paper kind's owner says when its sign-off must wait.

EBP-02 (`ebp_provisions`) signs off only once every provision is verified: assurance registers a
guard for the kind, and the paper's sign-off facts carry its code and count, so review answers
409 `sign_off_blocked` with `facts.reason` `provisions_unverified`. A guard that raises blocks
(fail closed).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from abacus.kernel.db import TenantContext

# (tenant, workpaper, work item) -> (code, count) while it must wait, else None
SignOffGuard = Callable[[TenantContext, UUID, UUID | None], Awaitable[tuple[str, int] | None]]
_GUARDS: dict[str, SignOffGuard] = {}


def register_sign_off_guard(kind: str, guard: SignOffGuard) -> None:
    known = _GUARDS.get(kind)
    if known is not None and known is not guard:
        raise ValueError(f"paper kind {kind!r} already has a sign-off guard")
    _GUARDS[kind] = guard


async def sign_off_block(
    tenant: TenantContext, kind: str | None, workpaper_id: UUID, work_item_id: UUID | None
) -> tuple[str, int] | None:
    guard = None if kind is None else _GUARDS.get(kind)
    if guard is None:
        return None
    try:
        return await guard(tenant, workpaper_id, work_item_id)
    except Exception:
        return ("owner_unavailable", 1)
