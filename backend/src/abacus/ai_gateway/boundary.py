"""The model data boundary (SPEC-026 AC-2; TASK-049; ADR-031; SPEC-036; TASK-075). PROTECTED.

The per-call layer, before any network call on a route other than `fake`:
- a synthetic firm passes (basis `synthetic`). Identity owns that fact and registers the check;
- any other firm passes only when all of SPEC-036's conditions hold (basis `client_data`): the
  route is `bedrock` with `model_data_boundary: client_data` (`route`); the provider terms register
  covers it today (`terms`, ADR-114); the firm has opted in (`firm`); the agent is cleared for
  client data (`agent`); the engagement isn't excluded (`engagement`, skipped without one); and the
  agent's stage for the firm is `shadow` or `live` (`stage`).

Module facts arrive by registration; an unregistered fact means refused. A refusal is audited with
its reason, counted, and raised as `DataBoundaryRefused`, never retried or rerouted.

One more reason applies on every route, for every firm: `pii_in_context` (ADR-167 §2), when the
assembled context holds an unmasked TIN form (`ai_gateway.pii`). It is audited with the context
part's name as well, never the value.

`tax_return_information` (P-06-T20 security review; DEC-324): for a firm that isn't synthetic, on
every real route, a call attributed to an engagement holding a `tax_return` work item is refused.
Tax-return information (§7216) may reach a model only with the client's consent, and C19 will
register that consent. Until then, none exists, so this fails closed for every agent. Engagements
registers the fact, uncached; unregistered means refused.

`consent_7216` (C19 condition 6; T-01-T11; ADR P-12): a call whose context names TRI data
subjects is refused unless every subject holds both `use` and `ai_disclosure` consents, signed
by every required signer and in force for the year. It is evaluated on every route, `fake`
included, and for every firm, before the synthetic pass: a synthetic tenant's TRI is gated too.
Organisations registers the check (`register_tri_consent_check`); unregistered, or a subject
that could not be resolved, means refused. Nothing is cached: a revocation takes effect on the
next call. Every allowed call writes a `tri.agent_read` access event per subject.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Final, Literal, NoReturn, cast
from uuid import UUID

from abacus.ai_gateway.admission import NotAdmitted
from abacus.ai_gateway.context import DataSubject
from abacus.kernel import provider_terms
from abacus.kernel.clock import now as business_now
from abacus.kernel.clock import system_now
from abacus.kernel.config import Route, settings
from abacus.kernel.controls import control_state
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent

SyntheticCheck = Callable[[TenantContext], Awaitable[bool]]
# SPEC-036: (firm) -> opted in; (firm, engagement) -> excluded; (firm, agent) -> stage.
FirmCheck = Callable[[TenantContext], Awaitable[bool]]
EngagementCheck = Callable[[TenantContext, UUID], Awaitable[bool]]
StageCheck = Callable[[TenantContext, str], Awaitable[str | None]]
AgentCheck = Callable[[str], bool]
# C19 condition 6: (firm, subjects, at) -> the consent ids that cover every subject, or None when
# any subject lacks `use` or `ai_disclosure` for its year (organisations; T-01-T11).
TriConsentCheck = Callable[
    [TenantContext, tuple[DataSubject, ...], datetime], Awaitable[tuple[UUID, ...] | None]
]
Reason = Literal[
    "route",
    "terms",
    "firm",
    "agent",
    "engagement",
    "stage",
    "pii_in_context",
    "tax_return_information",
    "ai_paused",
    "consent_7216",
]
# Audited by index: append only, so the indices already recorded keep their meaning.
REASONS: Final[tuple[Reason, ...]] = (
    "route",
    "terms",
    "firm",
    "agent",
    "engagement",
    "stage",
    "pii_in_context",
    "tax_return_information",  # P-06-T20 security review (DEC-324)
    "ai_paused",  # Q-01-T36 (P-66): the platform's or the firm's AI kill switch
    "consent_7216",  # T-01-T11 (C19 condition 6): TRI without both §7216 consents
)
CLIENT_DATA_ROUTES: Final[frozenset[Route]] = frozenset({"bedrock"})  # ADR-113
_CACHE_SECONDS: Final = 60.0
# How long this process keeps a firm's facts (opted in, excluded, stage). The API keeps them
# `_CACHE_SECONDS` and drops a firm's in the request that changes them (its one model call, a
# knowledge-search embedding, is refused for a real firm whatever the facts); a worker, which
# makes the agents' model calls, keeps none (`hold_facts_for(0)`; DEC-337), so no stale grant
# outlives a change made in another process.
_fact_seconds: float = _CACHE_SECONDS
_check: SyntheticCheck | None = None
_opted_in: FirmCheck | None = None
_excluded: EngagementCheck | None = None
_stage: StageCheck | None = None
_cleared: AgentCheck | None = None
_tax_return: EngagementCheck | None = None
_tri_consent: TriConsentCheck | None = None
_cache: dict[object, tuple[bool, float]] = {}
_facts: dict[tuple[object, ...], tuple[object, float]] = {}
_log = get_logger(__name__)
_refused = meter(__name__).create_counter(
    "abacus.ai.boundary_refused", description="Real-model calls refused at the data boundary"
)


class DataBoundaryRefused(Exception):
    """A real model was asked to see data it may not. Never retried or rerouted."""

    def __init__(self, message: str, reason: Reason = "route") -> None:
        super().__init__(message)
        self.reason: Reason = reason


@dataclass(frozen=True)
class Basis:
    """Why a real-route call was allowed, for its usage record (SPEC-036 §4.8)."""

    basis: Literal["synthetic", "client_data"]
    terms_version: str | None = None


def register_synthetic_tenants(check: SyntheticCheck) -> None:
    global _check
    if _check is not None and _check is not check:
        raise RuntimeError("the synthetic-tenant check is already registered")
    _check = check


def register_tri_consent_check(check: TriConsentCheck) -> None:
    """C19 condition 6: organisations answers whether TRI subjects hold both consents."""
    global _tri_consent
    if _tri_consent is not None and _tri_consent is not check:
        raise RuntimeError("the TRI consent check is already registered")
    _tri_consent = check


def tri_consent_registered() -> bool:
    """Whether condition 6 can pass at all (agent specs declaring `tri` need it)."""
    return _tri_consent is not None


async def enforce_tri_consent(
    tenant: TenantContext, route: Route, prompt: str, subjects: tuple[DataSubject, ...]
) -> tuple[UUID, ...]:
    """Condition 6, on every route and for every firm, before the synthetic pass: the consent
    ids covering the subjects, or audit, count and raise `consent_7216`. No subjects: ()."""
    if not subjects:
        return ()
    check = _tri_consent
    covered = (
        None
        if check is None or any(s.entity_id is None or s.tax_year is None for s in subjects)
        else await check(tenant, subjects, await business_now(tenant))
    )
    if covered is None:
        await _refuse(tenant, route, prompt, "consent_7216")
    return covered


def register_client_data_facts(
    *,
    opted_in: FirmCheck | None = None,
    excluded: EngagementCheck | None = None,
    stage: StageCheck | None = None,
    cleared: AgentCheck | None = None,
    tax_return: EngagementCheck | None = None,
) -> None:
    """SPEC-036: identity (opt-in), engagements (exclusion; whether an engagement holds
    tax-return information, DEC-324) and agents (stage, clearance)."""
    global _opted_in, _excluded, _stage, _cleared, _tax_return
    if tax_return is not None:
        _tax_return = tax_return
    if opted_in is not None:
        _opted_in = opted_in
    if excluded is not None:
        _excluded = excluded
    if stage is not None:
        _stage = stage
    if cleared is not None:
        _cleared = cleared


async def _synthetic(tenant: TenantContext) -> bool:
    if _check is None:
        return False
    now = time.monotonic()
    found = _cache.get(tenant.tenant_id)
    if found is not None and found[1] > now:
        return found[0]
    answer = await _check(tenant)
    _cache[tenant.tenant_id] = (answer, now + _CACHE_SECONDS)
    return answer


async def is_synthetic(tenant: TenantContext) -> bool:
    return await _synthetic(tenant)


async def _cached[T](key: tuple[object, ...], ask: Callable[[], Awaitable[T]]) -> T:
    now = time.monotonic()
    found = _facts.get(key)
    if found is not None and found[1] > now:
        return cast(T, found[0])  # stored by this function for `key`
    answer = await ask()
    if _fact_seconds > 0:
        _facts[key] = (answer, now + _fact_seconds)
    return answer


async def _client_data_refusal(
    tenant: TenantContext, route: Route, agent_id: str | None, engagement_id: UUID | None
) -> Reason | None:
    """SPEC-036 §4.2, in order: the first condition that fails, or None."""
    if route not in CLIENT_DATA_ROUTES or settings().model_data_boundary != "client_data":
        return "route"
    if provider_terms.covering(route, system_now().date()) is None:
        return "terms"
    opted_in = _opted_in
    if opted_in is None or not await _cached(("firm", tenant.tenant_id), lambda: opted_in(tenant)):
        return "firm"
    if agent_id is None or _cleared is None or not _cleared(agent_id):
        return "agent"
    if engagement_id is not None:
        excluded = _excluded
        if excluded is None or await _cached(
            ("engagement", tenant.tenant_id, engagement_id),
            lambda: excluded(tenant, engagement_id),
        ):
            return "engagement"
    stage = _stage
    found = (
        await _cached(("stage", tenant.tenant_id, agent_id), lambda: stage(tenant, agent_id))
        if stage is not None
        else None
    )
    if found not in ("shadow", "live"):
        return "stage"
    return None


async def _holds_tax_return(tenant: TenantContext, engagement_id: UUID) -> bool:
    """Fail closed: without the registered fact, every engagement may hold it. Not cached, so
    a work item added a moment ago counts at once."""
    held = _tax_return
    return True if held is None else await held(tenant, engagement_id)


async def enforce_boundary(
    tenant: TenantContext,
    route: Route,
    prompt: str,
    *,
    agent_id: str | None = None,
    engagement_id: UUID | None = None,
    subjects: tuple[DataSubject, ...] = (),
) -> Basis | None:
    """Return why `route` may see this firm's data (None for `fake`); else audit, count and
    raise with the reason. AI paused for the platform or the firm (Q-01-T36, `ai_pause`) refuses
    every route first, the fake one too; then TRI without both §7216 consents (`consent_7216`,
    every route and firm, before the synthetic pass); then an engagement its partner excluded
    refuses every route, for every firm (SPEC-036 AC-6). Every provider call passes here just
    before it leaves, so with AI paused none does once the controls cache (10 s) has caught
    up."""
    excluded = _excluded
    paused = await control_state("ai_pause", tenant.tenant_id)
    if paused == "unknown":
        # The switches can't be read: no call leaves (fail closed), but this is an outage, not
        # a pause, so the run waits and retries instead of ending (DEC-338, security review).
        raise NotAdmitted("controls_unavailable", 10)
    if paused == "on":
        await _refuse(tenant, route, prompt, "ai_paused")
    await enforce_tri_consent(tenant, route, prompt, subjects)
    reason: Reason | None
    if (
        engagement_id is not None
        and excluded is not None
        and await _cached(
            ("engagement", tenant.tenant_id, engagement_id),
            lambda: excluded(tenant, engagement_id),
        )
    ):
        reason = "engagement"
    elif route == "fake":
        return None
    elif await _synthetic(tenant):
        return Basis("synthetic")
    elif engagement_id is not None and await _holds_tax_return(tenant, engagement_id):
        reason = "tax_return_information"
    else:
        reason = await _client_data_refusal(tenant, route, agent_id, engagement_id)
    if reason is None:
        return Basis("client_data", provider_terms.version())
    await _refuse(tenant, route, prompt, reason)


async def _refuse(
    tenant: TenantContext,
    route: Route,
    prompt: str,
    reason: Reason,
    *,
    part: tuple[str, int] | None = None,
) -> NoReturn:
    """Count, log, audit and raise. `part` is the context part (name, index) a
    `pii_in_context` refusal found the value in; the value itself is never recorded."""
    _refused.add(1, {"route": route, "prompt": prompt, "reason": reason})
    fields: dict[str, object] = {"part": part[0]} if part is not None else {}
    _log.warning(
        "ai.boundary_refused",
        tenant_id=tenant.tenant_id,
        route=route,
        prompt=prompt,
        reason=reason,
        **fields,
    )
    after = (
        Ref(reason=REASONS.index(reason), part=part[1])
        if part is not None
        else Ref(reason=REASONS.index(reason))
    )
    async with uow(tenant) as tx:
        tx.record("ai.boundary_refused", target=Target("firm", tenant.tenant_id), after=after)
    raise DataBoundaryRefused(f"route {route!r} may not see this firm's data ({reason})", reason)


async def refuse_pii_in_context(
    tenant: TenantContext, route: Route, prompt: str, part: str, part_index: int
) -> NoReturn:
    """ADR-167 §2: the context holds an unmasked TIN form. Every route, every firm."""
    await _refuse(tenant, route, prompt, "pii_in_context", part=(part, part_index))


def hold_facts_for(seconds: float) -> None:
    """How long this process caches firm facts; 0 reads them fresh for every call (DEC-337)."""
    global _fact_seconds
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    _fact_seconds = seconds
    _facts.clear()


def clear_cache(tenant_id: UUID | None = None) -> None:
    """Forget cached facts: one firm's (opt-out, exclusion, promotion; SPEC-036 Q5), or all."""
    if tenant_id is None:
        _cache.clear()
        _facts.clear()
        return
    _cache.pop(tenant_id, None)
    for key in [k for k in _facts if k[1] == tenant_id]:
        _facts.pop(key, None)


class BoundaryFactsChanged(DomainEvent):
    """A firm's boundary facts changed (opt-in or out, an engagement's exclusion, an agent's
    stage; Q-02-T08). The process that made the change forgets them at once; the relay hands
    this to the worker, where agent runs call models, so it forgets them too instead of waiting
    out the cache period (SPEC-036 Q5). Identifiers only: the tenant is the outbox row's."""

    event_type: ClassVar[str] = "ai_boundary.facts_changed"


async def on_boundary_facts_changed(event: OutboxEvent) -> None:
    """Idempotent: forgetting twice is forgetting."""
    clear_cache(event.tenant_id)
