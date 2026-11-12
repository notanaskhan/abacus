"""Capability availability (P-10-T45; P-10 §4.3; SPEC-647; DEC-87, ADR-167; DEC-4303). PROTECTED.

`GET /v1/agents/capabilities?engagement_id=` answers, per installable v2 capability, whether a
person could start it here and, when not, the first reason code. It is computed from facts code
already holds and never calls a model, so no usage row is written:

1. `paused`: the firm paused its agents, or (on an engagement) the engagement's agent is paused.
2. `ai_policy_off`: the firm's effective AI policy governs it and sets autonomy level 0.
3. `ai_excluded`: AI is off for the engagement (SPEC-036's boundary fact).
4. `consent_7216`: the capability reads tax return information (`data_classes` holds `tri`)
   and the engagement's taxpayer lacks either §7216 consent for the return's year (C19; the
   Stein taxpayer's case). Without a tax year on the engagement it reads `consent_7216` too
   (fail closed).
5. `not_on_team`: the person may not start runs on the engagement (`agent_run.start`).

`TEST_ONLY` capabilities never appear for a real firm. Without `engagement_id` only the firm's
facts apply (1, 2). An engagement the person can't read answers 404 (a wall included).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import now
from abacus.kernel.db import tenant_session
from abacus.modules.agents.ai_policy_store import policy_autonomy_level
from abacus.modules.agents.spec_v2 import AGENTS_V2, TEST_ONLY, AgentSpecV2
from abacus.modules.engagements.api import ai_excluded, engagement_metadata, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    agents_paused,
    authorise,
    could,
    is_synthetic_firm,
)
from abacus.modules.organisations.api import TriSubject, covering_consents

REASONS: Final = (
    "paused",
    "ai_policy_off",
    "ai_excluded",
    "consent_7216",
    "not_on_team",
)


@dataclass(frozen=True)
class Availability:
    capability: str
    available: bool
    reason: str | None = None


# The engagement agent's pause is this module's own row (SPEC-027); the period is engagements'.
_PAUSED = text("SELECT paused_at IS NOT NULL FROM engagement_agents WHERE engagement_id = :e")


def _tri(spec: AgentSpecV2) -> bool:
    return "tri" in spec.data_classes


def installable(specs: Sequence[AgentSpecV2], synthetic: bool) -> list[AgentSpecV2]:
    return sorted((s for s in specs if synthetic or s.id not in TEST_ONLY), key=lambda s: s.id)


def first_reason(
    spec: AgentSpecV2,
    *,
    paused: bool,
    policy_off: bool,
    excluded: bool,
    consent: bool,
    may_start: bool,
    on_engagement: bool,
) -> str | None:
    """The first reason code in `REASONS` order, or None when the capability is available."""
    if paused:
        return "paused"
    if policy_off:
        return "ai_policy_off"
    if not on_engagement:
        return None
    if excluded:
        return "ai_excluded"
    if _tri(spec) and not consent:
        return "consent_7216"
    if not may_start:
        return "not_on_team"
    return None


async def capabilities_for(ctx: AuthContext, engagement_id: UUID | None) -> list[Availability]:
    synthetic = await is_synthetic_firm(ctx.tenant)
    specs = installable(list(AGENTS_V2.values()), synthetic)
    paused = await agents_paused(ctx.tenant) is not None
    level = await policy_autonomy_level(ctx.tenant_id)
    policy_off = level == 0
    excluded = consent = may_start = False
    if engagement_id is None:
        await authorise(ctx, "session.read", Resource.firm(ctx.tenant_id))
    if engagement_id is not None:
        ref = await get_ref(ctx, engagement_id)  # a wall answers 404
        await authorise(ctx, "session.read", ref.resource())
        async with tenant_session(ctx.tenant) as session:
            paused = paused or bool(await session.scalar(_PAUSED, {"e": engagement_id}))
        excluded = await ai_excluded(ctx.tenant, engagement_id)
        period = (await engagement_metadata(ctx, engagement_id)).engagement.fiscal_period_end
        year = period.year
        if any(_tri(s) for s in specs):
            covering = await covering_consents(
                ctx.tenant, [TriSubject(ref.client_entity_id, year)], await now(ctx.tenant)
            )
            consent = covering is not None
        may_start = await could(ctx, ctx.user_id, "agent_run.start", ref.resource())
    return [
        Availability(s.id, reason is None, reason)
        for s in specs
        for reason in (
            first_reason(
                s,
                paused=paused,
                policy_off=policy_off,
                excluded=excluded,
                consent=consent,
                may_start=may_start,
                on_engagement=engagement_id is not None,
            ),
        )
    ]


async def capability_ready(
    ctx: AuthContext, engagement_id: UUID, capability: str
) -> tuple[bool, str | None]:
    """P-10-T43/T-04-T37: whether `capability` may run on the engagement for this person now, and
    the reason when not (no model call). An unknown or test-only capability reads unavailable."""
    found = {a.capability: a for a in await capabilities_for(ctx, engagement_id)}
    hit = found.get(capability)
    if hit is None:
        return False, "capability_unavailable"
    return hit.available, hit.reason
