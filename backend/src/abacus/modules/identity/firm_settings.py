"""The firm's autonomy level and its onboarding acknowledgements (SPEC-024 AC-5, AC-7;
TASK-042). PROTECTED.

Autonomy (ADR-061) is per firm: 0 Advise, 1 Routine (new firms), 2 Manage, 3 Portfolio. Only
Advise and Routine can be chosen until the engagement agent exists (Q3). The level is read
fresh at every automatic action (`autonomy_level`): at Advise the platform starts nothing on
its own (Q4). Decisions stay human at every level (ADR-005).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from abacus.ai_gateway import forget_boundary_facts
from abacus.kernel import provider_terms
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import FirmAgentsResumed
from abacus.modules.identity.repository import (
    acknowledge_onboarding,
    agents_paused_since,
    ai_client_data,
    drafted_guidance_shown,
    firm_is_synthetic,
    firm_settings,
    letter_required,
    onboarding_counts,
    set_agents_paused,
    set_ai_client_data,
    set_autonomy_level,
    set_drafted_guidance_shown,
    set_letter_required,
    set_time_zone,
    time_zone_of,
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


DEFAULT_TIME_ZONE: Final = "America/New_York"


async def firm_time_zone(tenant: TenantContext) -> str:
    """SPEC-027 (TASK-051): the zone of the engagement agent's 09:00 business-day tick."""
    async with tenant_session(tenant) as session:
        return await time_zone_of(session)


async def read_time_zone(ctx: AuthContext) -> str:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    return await firm_time_zone(ctx.tenant)


class UnknownTimeZone(DomainInvalid):
    code = "unknown_time_zone"


async def set_firm_time_zone(ctx: AuthContext, zone: str) -> str:
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise UnknownTimeZone(zone) from None
    async with uow(ctx.tenant) as tx:
        await set_time_zone(tx.session, zone)
        tx.record("firm.time_zone_changed", target=Target("firm", ctx.tenant_id))
    return zone


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


@dataclass(frozen=True)
class AgentsState:
    paused_at: datetime | None


async def agents_paused(tenant: TenantContext) -> datetime | None:
    """SPEC-027 (TASK-050): whether the firm has paused every engagement agent (read fresh by
    each of the agent's policies)."""
    async with tenant_session(tenant) as session:
        return await agents_paused_since(session)


async def read_agents_state(ctx: AuthContext) -> AgentsState:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    return AgentsState(await agents_paused(ctx.tenant))


async def set_firm_agents_paused(ctx: AuthContext, paused: bool) -> AgentsState:
    """SPEC-027 AC-6: the firm-wide switch (firm administrator, fresh MFA). Resuming tells every
    agent to look at its engagement once (`firm.agents_resumed`)."""
    await authorise(ctx, "firm_agents.pause", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await set_agents_paused(tx.session, ctx.user_id if paused else None)
        tx.record(
            "firm.agents_paused" if paused else "firm.agents_resumed",
            target=Target("firm", ctx.tenant_id),
        )
        if not paused:
            tx.emit(FirmAgentsResumed())
    return AgentsState(await agents_paused(ctx.tenant))


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


# --- Drafted guidance for clients (SPEC-035 Q2; TASK-073 D2; ADR-111) --------------------------


class DraftedGuidanceNotAllowed(DomainConflict):
    """Only synthetic firms may show drafted guidance to clients while the data boundary holds
    (ADR-112)."""

    code = "drafted_guidance_not_allowed"


async def drafted_guidance_to_clients(tenant: TenantContext) -> bool:
    """Read fresh where the client's request list is built; never true for a real firm."""
    async with tenant_session(tenant) as session:
        return await drafted_guidance_shown(session) and await firm_is_synthetic(session)


async def read_drafted_guidance_setting(ctx: AuthContext) -> bool:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    return await drafted_guidance_to_clients(ctx.tenant)


async def set_drafted_guidance_setting(ctx: AuthContext, shown: bool) -> bool:
    """A firm administrator, with fresh MFA; refused for a real firm (ADR-111, ADR-112)."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    if shown and not await is_synthetic_firm(ctx.tenant):
        raise DraftedGuidanceNotAllowed(str(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await set_drafted_guidance_shown(tx.session, shown)
        tx.record(
            "firm.drafted_guidance_setting_changed",
            target=Target("firm", ctx.tenant_id),
            after=Ref(shown=int(shown)),
        )
    return shown


# --- AI on clients' data (SPEC-036; TASK-076) ---------------------------------------------------

# D4 (founder-approved, 2026-10-18): suggested wording for the firm's engagement letters (Q6).
LETTER_WORDING: Final = (
    "We use AI assistants, run by Amazon Web Services in the United States under terms that "
    "prohibit training on or retaining your data, to help review the documents you provide; our "
    "team reviews all of their work."
)
CLIENT_DATA_ROUTE: Final = "bedrock"  # ADR-113


class AiClientDataUnavailable(DomainConflict):
    """No provider terms entry covers Bedrock today (ADR-114): nothing to opt in against."""

    code = "ai_client_data_unavailable"


@dataclass(frozen=True)
class Assistant:
    agent_id: str
    purpose: str
    stage: str  # shadow | live | off


# Agents tells identity which assistants are cleared and their stage for a firm (ADR-106).
AssistantsSource = Callable[[TenantContext], Awaitable[list[Assistant]]]
_assistants: AssistantsSource | None = None


def register_ai_assistants(source: AssistantsSource) -> None:
    global _assistants
    _assistants = source


@dataclass(frozen=True)
class Disclosure:
    """What a firm opts in against, generated from the register's entry (ADR-114 §4)."""

    provider: str
    region: str
    retention_exceptions: tuple[tuple[str, int], ...]
    subprocessors: tuple[str, ...]
    review_by: date
    letter_wording: str


@dataclass(frozen=True)
class AiClientDataView:
    available: bool
    opted_in_at: datetime | None
    opted_in_by: UUID | None
    current: bool  # opted in against today's terms
    lapsed: bool  # opted in, but the terms changed materially since (Q4)
    disclosure: Disclosure | None
    assistants: tuple[Assistant, ...]


def _terms() -> provider_terms.TermsEntry | None:
    return provider_terms.covering(CLIENT_DATA_ROUTE, date.today())


async def ai_client_data_opted_in(tenant: TenantContext) -> bool:
    """For the gateway (SPEC-036 §4.2 `firm`): opted in against today's material terms."""
    terms = _terms()
    if terms is None:
        return False
    async with tenant_session(tenant) as session:
        found = await ai_client_data(session)
    return found.material is not None and found.material == terms.material


async def read_ai_client_data(ctx: AuthContext) -> AiClientDataView:
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    terms = _terms()
    async with tenant_session(ctx.tenant) as session:
        found = await ai_client_data(session)
    current = terms is not None and found.material == terms.material
    assistants = tuple(await _assistants(ctx.tenant)) if _assistants is not None else ()
    return AiClientDataView(
        available=terms is not None,
        opted_in_at=found.at,
        opted_in_by=found.by,
        current=current,
        lapsed=found.material is not None and not current,
        disclosure=Disclosure(
            terms.provider,
            terms.region,
            terms.retention_exceptions,
            terms.subprocessors,
            terms.review_by,
            LETTER_WORDING,
        )
        if terms is not None
        else None,
        assistants=assistants,
    )


async def set_ai_client_data_setting(ctx: AuthContext, on: bool) -> AiClientDataView:
    """AC-3: a firm administrator with fresh MFA. On records who, when and the terms' material
    fingerprint; off clears it, and the firm's cached boundary facts go in this request (Q5)."""
    await authorise(ctx, "firm.ai_client_data", Resource.firm(ctx.tenant_id))
    terms = _terms()
    if on and terms is None:
        raise AiClientDataUnavailable(str(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await set_ai_client_data(
            tx.session,
            ctx.user_id if on else None,
            terms.material if on and terms is not None else None,
        )
        tx.record(
            "firm.ai_client_data_on" if on else "firm.ai_client_data_off",
            target=Target("firm", ctx.tenant_id),
        )
    forget_boundary_facts(ctx.tenant_id)
    return await read_ai_client_data(ctx)
