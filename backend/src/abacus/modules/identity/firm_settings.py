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
from time import monotonic
from typing import Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from abacus.ai_gateway import forget_boundary_facts
from abacus.kernel import clock, provider_terms
from abacus.kernel._flags import AGENTS_CLIENT_DATA_OPTIN
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.authz.matrix import STORED_SETTING_KEYS
from abacus.modules.identity.authz.overrides import refusal
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import FirmAgentsResumed
from abacus.modules.identity.repository import (
    DemoClockRow,
    acknowledge_onboarding,
    agents_paused_since,
    ai_client_data,
    demo_clock_row,
    drafted_guidance_shown,
    firm_is_synthetic,
    firm_settings,
    firm_tenancy_row,
    insert_policy_override,
    letter_required,
    onboarding_counts,
    set_agents_paused,
    set_ai_client_data,
    set_autonomy_level,
    set_demo_clock_row,
    set_drafted_guidance_shown,
    set_letter_required,
    set_time_zone,
    time_zone_of,
    upsert_firm_setting,
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


@dataclass(frozen=True)
class FirmTenancy:
    """Q-01-T45 (ADR-156): what provisioning set on the firm. A firm whose key is not
    `replica_verified` stores no client content."""

    synthetic: bool
    region: str
    kms_key_status: str
    kms_replica_verified_at: datetime | None
    created_at: datetime


async def firm_tenancy(tenant: TenantContext) -> FirmTenancy | None:
    """The firm's tenancy facts under its row-level security, or None if it doesn't exist."""
    async with tenant_session(tenant) as session:
        row = await firm_tenancy_row(session)
    if row is None:
        return None
    return FirmTenancy(
        bool(row["synthetic"]),
        str(row["region"]),
        str(row["kms_key_status"]),
        row["kms_replica_verified_at"],
        row["created_at"],
    )


TenantKeyStatus = Literal["active", "replica_verified"]
_RECORD_KEY = text(
    "UPDATE firms SET kms_key_arn = :arn, kms_key_status = :status, "
    "kms_replica_verified_at = CASE WHEN :status = 'replica_verified' "
    "THEN clock_timestamp() ELSE kms_replica_verified_at END "
    "WHERE kms_key_status IN ('none', 'pending', 'active', 'replica_verified')"
)


async def record_tenant_key(ctx: TenantContext, *, arn: str, status: TenantKeyStatus) -> None:
    """Q-01-T27: the firm's tenant key, as the keyops workflow made it (the firm's own row,
    under its row-level security). `replica_verified` is what lets the firm store client content
    (ADR-156). A key scheduled for deletion is never brought back here. Audited."""
    if not arn.startswith("arn:aws:kms:") or len(arn) > 300:
        raise ValueError("a tenant key is a KMS key ARN")
    async with uow(ctx) as tx:
        await tx.session.execute(_RECORD_KEY, {"arn": arn, "status": status})
        tx.record(
            "tenant_key.recorded",
            target=Target("firm", ctx.tenant_id),
            after=Ref(verified=int(status == "replica_verified")),
        )


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
    return provider_terms.covering(CLIENT_DATA_ROUTE, system_now().date())


async def _require_optin_flag(tenant: TenantContext) -> None:
    if not await flag_enabled(tenant, AGENTS_CLIENT_DATA_OPTIN):
        raise NotFound(AGENTS_CLIENT_DATA_OPTIN.name)


async def ai_client_data_opted_in(tenant: TenantContext) -> bool:
    """For the gateway (SPEC-036 §4.2 `firm`): opted in against today's material terms, with
    the opt-in flag on (off is fail-closed: not opted in)."""
    terms = _terms()
    if terms is None or not await flag_enabled(tenant, AGENTS_CLIENT_DATA_OPTIN, fresh=True):
        return False
    async with tenant_session(tenant) as session:
        found = await ai_client_data(session)
    return found.material is not None and found.material == terms.material


async def read_ai_client_data(ctx: AuthContext) -> AiClientDataView:
    await _require_optin_flag(ctx.tenant)
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
    fingerprint; off clears it, and the firm's cached boundary facts go in this request (Q5).
    Flag off: opting in answers 404, like the read; opting out is always allowed (DEC-367)."""
    if on:
        await _require_optin_flag(ctx.tenant)
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


# --- F-03-T24: firm setting values and stricter-only policy overrides (DEC-127) ---------------


class UnknownFirmSetting(DomainInvalid):
    """Only the registered keys: those a matrix cell can name and the stricter-only ones
    (`authz.matrix.STORED_SETTING_KEYS`)."""

    code = "unknown_firm_setting"


class OverrideRefused(DomainConflict):
    """A firm override may only narrow a matrix cell (`authz.overrides.refusal` says why)."""

    code = "override_refused"


async def set_firm_setting(ctx: AuthContext, key: str, value: bool) -> int:
    """Switch a registered firm setting on or off (firm administrator, fresh MFA); its version
    afterwards. Read by `authorise` from the next request."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    if key not in STORED_SETTING_KEYS:
        raise UnknownFirmSetting
    async with uow(ctx.tenant) as tx:
        version = await upsert_firm_setting(
            tx.session, tenant_id=ctx.tenant_id, key=key, value=value, set_by=ctx.user_id
        )
        tx.record(
            "firm_setting.set",
            target=Target("firm", ctx.tenant_id),
            after=Ref(value=int(value), version=version),
        )
    return version


async def set_policy_override(
    ctx: AuthContext, action: str, role: str, *, reason: str, decision: str = "deny"
) -> bool:
    """Narrow one matrix cell for the firm (firm administrator, fresh MFA). Refused when it
    would widen the cell, or when it couldn't be enforced (a read, a platform role, no cell).
    Whether a row was written (False: the cell was already overridden)."""
    await authorise(ctx, "firm.manage_settings", Resource.firm(ctx.tenant_id))
    why = refusal(action, role, decision)
    if why is not None:
        raise OverrideRefused(facts={"reason": why})
    if not reason.strip():
        raise DomainInvalid
    async with uow(ctx.tenant) as tx:
        written = await insert_policy_override(
            tx.session,
            tenant_id=ctx.tenant_id,
            action=action,
            role=role,
            decision=decision,
            reason=reason.strip()[:500],
            set_by=ctx.user_id,
        )
        tx.record("firm_policy_override.set", target=Target("firm", ctx.tenant_id))
    return written


# --- F-04-T07: the tenant demo clock (ADR-143; synthetic firms outside production) ------------

DemoClockMode = Literal["offset", "frozen"]
ClockMode = Literal["real", "offset", "frozen"]
# Each firm's demo clock, read at most once per window per process: the business clock asks on
# every tenant transaction outside production (F-04-T06).
_CLOCK_CACHE_SECONDS: Final = 5.0
_clocks: dict[UUID, tuple[float, DemoClockRow | None]] = {}


class DemoClockRefused(DomainConflict):
    """A demo clock is only for a synthetic firm, and never in production (F-04.2, F-04.3)."""

    code = "demo_clock_refused"


def forget_demo_clocks() -> None:
    """Drop the cached clocks (after a change; tests)."""
    _clocks.clear()


async def _clock_row(tenant: TenantContext) -> DemoClockRow | None:
    seen = _clocks.get(tenant.tenant_id)
    now_mono = monotonic()
    if seen is not None and now_mono - seen[0] < _CLOCK_CACHE_SECONDS:
        return seen[1]
    async with tenant_session(tenant) as session:
        row = await demo_clock_row(session, tenant.tenant_id)
    _clocks[tenant.tenant_id] = (now_mono, row)
    return row


def _business(row: DemoClockRow) -> datetime:
    if row.mode == "frozen":
        return row.anchor_at
    return row.anchor_at + (clock.system_now() - row.anchored_real_at)


async def tenant_demo_time(tenant: TenantContext) -> datetime | None:
    """The firm's demo time, or None (no demo clock): `kernel.clock`'s tenant provider. The
    clock never asks in production; the database ignores it for a real firm anyway."""
    row = await _clock_row(tenant)
    return None if row is None else _business(row)


@dataclass(frozen=True)
class ClockView:
    server_now: datetime
    clock_mode: ClockMode


async def clock_view(tenant: TenantContext | None) -> ClockView:
    """`/v1/me`'s `server_now` and `clock_mode` for the caller's tenant (F-04-T07)."""
    business = await clock.now(tenant)
    mode: ClockMode = "real"
    if tenant is not None and settings().environment != "production":
        row = await _clock_row(tenant)
        if row is not None:
            mode = cast(ClockMode, row.mode)
    return ClockView(business, mode)


async def set_demo_clock(
    ctx: AuthContext, mode: DemoClockMode | None, anchor_at: datetime | None = None
) -> ClockView:
    """Set (`offset` runs from `anchor_at`, `frozen` stands at it) or reset (`mode=None`) the
    firm's demo clock. Firm administrator; refused in production and for a real firm; audited
    as `firm.demo_clock_changed`. Called by the scenario loader and the runbook, never HTTP."""
    await authorise(ctx, "demo_clock.set", Resource.firm(ctx.tenant_id))
    if settings().environment == "production":
        raise DemoClockRefused
    if mode is not None and (anchor_at is None or anchor_at.tzinfo is None):
        raise DomainInvalid
    async with uow(ctx.tenant) as tx:
        if not await firm_is_synthetic(tx.session):
            raise DemoClockRefused
        await set_demo_clock_row(tx.session, ctx.tenant_id, mode, anchor_at, str(ctx.user_id))
        tx.record("firm.demo_clock_changed", target=Target("firm", ctx.tenant_id))
    forget_demo_clocks()
    return await clock_view(ctx.tenant)
