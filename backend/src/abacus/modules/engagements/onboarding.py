"""The firm's onboarding checklist (SPEC-024 AC-7; TASK-042).

Every step is computed from the firm's data, never stored as done: identity's facts (staff,
invitations, walls, the acknowledgements) through its API, and this module's methodology
templates and engagements (D2). SSO is held for the identity vendor decision, so its step can
only be skipped for now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.repository import setup_counts
from abacus.modules.identity.api import AuthContext, acknowledge, firm_facts

StepId = Literal["sso", "team", "methodology", "autonomy", "budget", "walls", "engagement"]
ORDER: Final[tuple[StepId, ...]] = (
    "sso",
    "team",
    "methodology",
    "autonomy",
    "budget",
    "walls",
    "engagement",
)


@dataclass(frozen=True)
class Step:
    id: StepId
    done: bool
    # How it was completed when that matters to the page: "skipped" or "none_needed".
    how: str | None = None


@dataclass(frozen=True)
class Onboarding:
    steps: tuple[Step, ...]
    dismissed: bool

    @property
    def complete(self) -> bool:
        return all(step.done for step in self.steps)


async def onboarding(ctx: AuthContext) -> Onboarding:
    facts = await firm_facts(ctx)  # authorises `firm.read_settings`
    async with tenant_session(ctx.tenant) as session:
        templates, engagements = await setup_counts(session)
    steps = {
        "sso": Step("sso", facts.sso_skipped_at is not None, "skipped"),
        "team": Step("team", facts.staff > 1 or facts.invitations > 0),
        "methodology": Step("methodology", templates > 0),
        "autonomy": Step("autonomy", facts.autonomy_set_at is not None),
        "budget": Step("budget", facts.budget_reviewed_at is not None),
        "walls": Step(
            "walls",
            facts.walls > 0 or facts.walls_none_needed_at is not None,
            "none_needed" if facts.walls == 0 and facts.walls_none_needed_at else None,
        ),
        "engagement": Step("engagement", engagements > 0),
    }
    return Onboarding(tuple(steps[s] for s in ORDER), facts.dismissed_at is not None)


async def acknowledge_step(
    ctx: AuthContext, step: Literal["sso", "budget", "walls"]
) -> Onboarding:
    await acknowledge(ctx, step)  # authorises `firm.manage_settings` (fresh MFA), audited
    return await onboarding(ctx)


async def dismiss(ctx: AuthContext) -> Onboarding:
    await acknowledge(ctx, "dismiss")
    return await onboarding(ctx)
