"""The firm's autonomy level and its onboarding acknowledgements (SPEC-024 AC-5, AC-7;
TASK-042). PROTECTED.

Autonomy (ADR-061) is per firm: 0 Advise, 1 Routine (new firms), 2 Manage, 3 Portfolio. Only
Advise and Routine can be chosen until the engagement agent exists (Q3). The level is read
fresh at every automatic action (`autonomy_level`): at Advise the platform starts nothing on
its own (Q4). Decisions stay human at every level (ADR-005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import (
    acknowledge_onboarding,
    firm_is_synthetic,
    firm_settings,
    letter_required,
    onboarding_counts,
    set_autonomy_level,
    set_letter_required,
)

ROUTINE: Final = 1
SELECTABLE: Final = frozenset({0, 1})
Acknowledgement = Literal["budget", "walls", "sso", "dismiss"]


class LevelNotAvailable(DomainConflict):
    """Manage and Portfolio come with the engagement agent (SPEC-024 Q3)."""

    code = "level_not_available"


@dataclass(frozen=True)
class AutonomyView:
    level: int
    set_at: datetime | None


@dataclass(frozen=True)
class FirmFacts:
    """What the onboarding checklist needs from identity (SPEC-024 AC-7)."""

    autonomy_set_at: datetime | None
    budget_reviewed_at: datetime | None
    walls_none_needed_at: datetime | None
    sso_skipped_at: datetime | None
    dismissed_at: datetime | None
    staff: int
    invitations: int
    walls: int


async def autonomy_level(tenant_id: UUID) -> int:
    """The firm's level now, for the platform's automatic actions (Routine if unreadable)."""
    async with tenant_session(TenantContext(tenant_id, "system", "autonomy")) as session:
        row = await firm_settings(session)
    return int(row["autonomy_level"]) if row is not None else ROUTINE


async def autonomy(ctx: AuthContext) -> AutonomyView:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        row = await firm_settings(session)
    if row is None:
        return AutonomyView(ROUTINE, None)
    return AutonomyView(int(row["autonomy_level"]), row["autonomy_set_at"])


async def set_autonomy(ctx: AuthContext, level: int) -> AutonomyView:
    """AC-5: fresh MFA; audited; Manage and Portfolio refused for now."""
    await authorise(ctx, "autonomy_policy.update", Resource.firm(ctx.tenant_id))
    if level not in SELECTABLE:
        raise LevelNotAvailable(str(level))
    async with uow(ctx.tenant) as tx:
        before = await firm_settings(tx.session)
        await set_autonomy_level(tx.session, level)
        tx.record(
            "autonomy_policy.updated",
            target=Target("firm", ctx.tenant_id),
            before=Ref(level=int(before["autonomy_level"])) if before is not None else None,
            after=Ref(level=level),
        )
    return await autonomy(ctx)


async def firm_facts(ctx: AuthContext) -> FirmFacts:
    """For the checklist (engagements composes it), after `firm.read_settings`."""
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        row = await firm_settings(session)
        counts = await onboarding_counts(session)
    return FirmFacts(
        row["autonomy_set_at"] if row else None,
        row["budget_reviewed_at"] if row else None,
        row["walls_none_needed_at"] if row else None,
        row["sso_skipped_at"] if row else None,
        row["onboarding_dismissed_at"] if row else None,
        int(counts["staff"]),
        int(counts["invitations"]),
        int(counts["walls"]),
    )


async def acknowledge(ctx: AuthContext, step: Acknowledgement) -> None:
    """A step the administrator confirms (budget looks right, no walls needed, SSO skipped) or
    the checklist's dismissal; fresh MFA (`firm.manage_settings`), audited."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await acknowledge_onboarding(tx.session, step)
        tx.record(
            "onboarding.acknowledged",
            target=Target("firm", ctx.tenant_id),
            after=Ref(step=["budget", "walls", "sso", "dismiss"].index(step) + 1),
        )


async def note_budget_reviewed(tx: UnitOfWork) -> None:
    """Inside the caller's unit of work, after its `budget.manage`: setting a budget also
    completes the checklist's budget step (the caller's own event audits the change)."""
    await acknowledge_onboarding(tx.session, "budget")


# --- The engagement letter before client data (SPEC-025 Q4; TASK-044) --------------------------


async def is_synthetic_firm(tenant: TenantContext) -> bool:
    """SPEC-026 AC-2 (TASK-049): for the AI gateway's data boundary. A firm is synthetic only
    when the local seed or an evaluation run marked it, through the owner role."""
    async with tenant_session(tenant) as session:
        return await firm_is_synthetic(session)


async def letter_policy(tenant: TenantContext) -> bool:
    """Whether the firm requires the letter before client data (the gate reads it)."""
    async with tenant_session(tenant) as session:
        return await letter_required(session)


async def read_letter_policy(ctx: AuthContext) -> bool:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    return await letter_policy(ctx.tenant)


async def set_letter_policy(ctx: AuthContext, required: bool) -> bool:
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await set_letter_required(tx.session, required)
        tx.record(
            "firm.letter_policy_changed",
            target=Target("firm", ctx.tenant_id),
            after=Ref(required=int(required)),
        )
    return required
