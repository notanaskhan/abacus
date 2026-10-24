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
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Literal, NoReturn, cast
from uuid import UUID

from abacus.kernel import provider_terms
from abacus.kernel.clock import system_now
from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow

SyntheticCheck = Callable[[TenantContext], Awaitable[bool]]
# SPEC-036: (firm) -> opted in; (firm, engagement) -> excluded; (firm, agent) -> stage.
FirmCheck = Callable[[TenantContext], Awaitable[bool]]
EngagementCheck = Callable[[TenantContext, UUID], Awaitable[bool]]
StageCheck = Callable[[TenantContext, str], Awaitable[str | None]]
AgentCheck = Callable[[str], bool]
Reason = Literal["route", "terms", "firm", "agent", "engagement", "stage", "pii_in_context"]
# Audited by index: append only, so the indices already recorded keep their meaning.
REASONS: Final[tuple[Reason, ...]] = (
    "route",
    "terms",
    "firm",
    "agent",
    "engagement",
    "stage",
    "pii_in_context",
)
CLIENT_DATA_ROUTES: Final[frozenset[Route]] = frozenset({"bedrock"})  # ADR-113
_CACHE_SECONDS: Final = 60.0
_check: SyntheticCheck | None = None
_opted_in: FirmCheck | None = None
_excluded: EngagementCheck | None = None
_stage: StageCheck | None = None
_cleared: AgentCheck | None = None
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


def register_client_data_facts(
    *,
    opted_in: FirmCheck | None = None,
    excluded: EngagementCheck | None = None,
    stage: StageCheck | None = None,
    cleared: AgentCheck | None = None,
) -> None:
    """SPEC-036: identity (opt-in), engagements (exclusion) and agents (stage, clearance)."""
    global _opted_in, _excluded, _stage, _cleared
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
    _facts[key] = (answer, now + _CACHE_SECONDS)
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


async def enforce_boundary(
    tenant: TenantContext,
    route: Route,
    prompt: str,
    *,
    agent_id: str | None = None,
    engagement_id: UUID | None = None,
) -> Basis | None:
    """Return why `route` may see this firm's data (None for `fake`); else audit, count and
    raise with the reason. An engagement its partner excluded refuses every route, for every
    firm (SPEC-036 AC-6)."""
    excluded = _excluded
    if (
        engagement_id is not None
        and excluded is not None
        and await _cached(
            ("engagement", tenant.tenant_id, engagement_id),
            lambda: excluded(tenant, engagement_id),
        )
    ):
        reason: Reason | None = "engagement"
    elif route == "fake":
        return None
    elif await _synthetic(tenant):
        return Basis("synthetic")
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


def clear_cache(tenant_id: UUID | None = None) -> None:
    """Forget cached facts: one firm's (opt-out, exclusion, promotion; SPEC-036 Q5), or all."""
    if tenant_id is None:
        _cache.clear()
        _facts.clear()
        return
    _cache.pop(tenant_id, None)
    for key in [k for k in _facts if k[1] == tenant_id]:
        _facts.pop(key, None)
