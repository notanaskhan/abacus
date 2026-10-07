"""The AI gateway (ADR-019, ADR-050, ADR-070). PROTECTED. TASK-011 design §2.

Every model call goes through `call`. A call declares its purpose, prompt (`id@version`), tier,
output schema, budget and attribution (firm, engagement, agent, run); anything missing is
refused. The gateway renders the registered prompt with an `AssembledContext` (the only input
type), routes by tier, validates the output against the schema, repairs once with the validation
errors, then escalates. Every provider call writes a usage record (AC-16) and a log line with the
model, prompt version, inputs hash and outcome; the output itself is the caller's to store.

For an agent run, `budget_usd` is the run's budget: what earlier calls for the same run already
spent (its usage records, including retried attempts) counts against it (ADR-070).

`call` records usage in its own unit of work, committed per attempt so spend survives a later
failure: never call it inside a unit of work (the kernel refuses nesting).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from decimal import Decimal
from math import ceil
from typing import Literal, cast
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import Status as SpanStatus
from opentelemetry.trace import StatusCode
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from abacus.ai_gateway._eval_suites import EVAL_SUITES
from abacus.ai_gateway.admission import (
    CallTooLarge,
    NotAdmitted,
    admit,
    block,
    refusal_reason,
)
from abacus.ai_gateway.budgets import BudgetExhausted, check_budget, forget_spend
from abacus.ai_gateway.context import (
    MAX_ROWS,
    AssembledContext,
    ContextBuilder,
    ContextTooLarge,
    DatasetTooLarge,
    estimate_tokens,
)
from abacus.ai_gateway.embeddings import (
    EMBED_PROMPT,
    MAX_TEXT_CHARS,
    MAX_TEXTS,
    EmbeddingProvider,
    EmbeddingResponse,
    EmbedResult,
    EmbedTooLarge,
    FakeEmbedder,
    configure_embedder,
    embed_cost,
    embedder,
    embedding_route,
)
from abacus.ai_gateway.prompts import Prompt, UnknownPrompt, prompt, registry
from abacus.ai_gateway.providers import (
    FakeModel,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderError,
    Tier,
    configure_provider,
)
from abacus.ai_gateway.routes import configure_route, model_id, route_enabled, route_provider
from abacus.ai_gateway.sanitise import sanitise_text
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, Route, settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.telemetry import tracer
from abacus.kernel.uow import Target, uow
from abacus.kernel.work_class import WorkClass

# The fake route's models (synthetic environments, tests and tooling), per million tokens (input,
# output), by tier. Prices for every route come from `settings().model_catalog` (SPEC-010).
MODELS: dict[Tier, tuple[str, Decimal, Decimal]] = {
    "small": ("fake-small", Decimal("0.80"), Decimal("4.00")),
    "medium": ("fake-medium", Decimal("3.00"), Decimal("15.00")),
    "large": ("fake-large", Decimal("15.00"), Decimal("75.00")),
}
_MILLION = Decimal(1_000_000)
_log = get_logger(__name__)
_tracer = tracer(__name__)
_failovers = meter(__name__).create_counter(
    "abacus.ai.failovers", description="Attempts handed to the next route, by route and reason"
)

Outcome = Literal["ok", "invalid", "repaired", "budget_refused", "provider_error", "rate_limited"]
Status = Literal["ok", "repaired", "escalated"]


class GatewayRefused(ValueError):
    """The call is missing something the gateway requires, or breaks a rule (ADR-019)."""


class BudgetExceeded(Exception):
    """The call (or its repair) would cost more than its budget."""


@dataclass(frozen=True)
class Attribution:
    """Who pays and why (ADR-070): firm, engagement, agent and run."""

    tenant: TenantContext
    engagement_id: UUID | None
    agent_id: str
    agent_run_id: UUID | None


@dataclass(frozen=True)
class GatewayCall[T: BaseModel]:
    purpose: str
    prompt: str
    tier: Tier
    output_schema: type[T]
    budget_usd: Decimal
    attribution: Attribution
    context: AssembledContext
    # Admission (ADR-072, SPEC-003): the caller's work class and whether it is essential (ADR-069
    # as named by ADR-105). Required: no call gets a priority by default.
    work_class: WorkClass
    essential: bool
    # SPEC-010 (ADR-073): the agent's allowed routes, in preference order (from its spec). In
    # synthetic environments the fake route serves every call.
    routes: tuple[Route, ...]
    max_output_tokens: int = 1_000
    # Per provider call; exceeding it is a provider error (retryable by the caller).
    timeout_seconds: float = 60
    # Cheaper tiers the call may step down to under pressure (its spec's, ADR-072).
    cheaper_tiers: tuple[Tier, ...] = ()


@dataclass(frozen=True)
class GatewayResult[T: BaseModel]:
    status: Status
    output: T | None
    attempts: int
    cost_usd: Decimal
    inputs_hash: str
    model: str
    prompt: Prompt
    route: Route = "fake"


def cost(tier: Tier, input_tokens: int, output_tokens: int) -> Decimal:
    entry = settings().model_catalog[tier]
    per_in, per_out = entry.usd_in, entry.usd_out
    return ((per_in * input_tokens + per_out * output_tokens) / _MILLION).quantize(
        Decimal("0.000001")
    )


def _check[T: BaseModel](c: GatewayCall[T]) -> Prompt:
    if not c.purpose.strip():
        raise GatewayRefused("a call declares its purpose")
    schema = cast(object, c.output_schema)  # checked at runtime: callers aren't always typed
    if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise GatewayRefused("a call declares a Pydantic output schema")
    if c.budget_usd <= 0:
        raise GatewayRefused("a call declares a positive budget")
    if c.tier not in MODELS:
        raise GatewayRefused("unknown tier")
    tenant = cast(object, c.attribution.tenant)
    if not isinstance(tenant, TenantContext) or not c.attribution.agent_id:
        raise GatewayRefused("a call is attributed to a firm and an agent")
    try:
        return prompt(c.prompt)
    except UnknownPrompt:
        raise GatewayRefused(f"prompt {c.prompt} is not registered") from None


async def _record_usage(
    attribution: Attribution,
    *,
    found: Prompt,
    model: str,
    tier: Tier,
    response: ModelResponse | None,
    spent: Decimal,
    outcome: Outcome,
    inputs_hash: str,
    route: Route,
) -> None:
    record_id = uuid4()
    async with uow(attribution.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO usage_records (id, tenant_id, engagement_id, agent_id, "
                "agent_run_id, prompt_id, prompt_version, model, tier, input_tokens, "
                "output_tokens, cost_usd, outcome, inputs_hash, route) VALUES (:id, :tenant, "
                ":engagement, :agent, :run, :prompt_id, :prompt_version, :model, :tier, "
                ":input_tokens, :output_tokens, :cost, :outcome, :inputs_hash, :route)"
            ),
            {
                "id": record_id,
                "tenant": attribution.tenant.tenant_id,
                "engagement": attribution.engagement_id,
                "agent": attribution.agent_id,
                "run": attribution.agent_run_id,
                "prompt_id": found.id,
                "prompt_version": found.version,
                "model": model,
                "tier": tier,
                "input_tokens": response.input_tokens if response else 0,
                "output_tokens": response.output_tokens if response else 0,
                "cost": spent,
                "outcome": outcome,
                "inputs_hash": inputs_hash,
                "route": route,
            },
        )
        tx.record("model.called", target=Target("usage_record", record_id))
    trace.get_current_span().add_event(
        "ai.attempt",
        {
            "route": route,
            "outcome": outcome,
            "input_tokens": response.input_tokens if response else 0,
            "output_tokens": response.output_tokens if response else 0,
            "cost_usd": str(spent),
        },
    )
    _log.info(
        "ai.call",
        prompt=found.ref,
        route=route,
        model=model,
        tier=tier,
        outcome=outcome,
        inputs_hash=inputs_hash,
        input_tokens=response.input_tokens if response else 0,
        output_tokens=response.output_tokens if response else 0,
        cost_usd=str(spent),
    )
    forget_spend()


# --- Embeddings (SPEC-009 AC-5; TASK-024 D1) -----------------------------------------------------


@dataclass(frozen=True)
class EmbedCall:
    purpose: str
    texts: tuple[str, ...]
    attribution: Attribution
    work_class: WorkClass
    essential: bool
    budget_usd: Decimal


async def _record_embed(
    attribution: Attribution,
    model: str,
    input_tokens: int,
    spent: Decimal,
    outcome: Outcome,
    inputs_hash: str,
) -> None:
    record_id = uuid4()
    async with uow(attribution.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO usage_records (id, tenant_id, engagement_id, agent_id, "
                "agent_run_id, prompt_id, prompt_version, model, tier, input_tokens, "
                "output_tokens, cost_usd, outcome, inputs_hash, route) VALUES (:id, :tenant, "
                ":engagement, :agent, :run, :prompt_id, '1', :model, 'small', :input_tokens, "
                "0, :cost, :outcome, :inputs_hash, :route)"
            ),
            {
                "id": record_id,
                "tenant": attribution.tenant.tenant_id,
                "engagement": attribution.engagement_id,
                "agent": attribution.agent_id,
                "run": attribution.agent_run_id,
                "prompt_id": EMBED_PROMPT,
                "route": embedding_route(),
                "model": model,
                "input_tokens": input_tokens,
                "cost": spent,
                "outcome": outcome,
                "inputs_hash": inputs_hash,
            },
        )
        tx.record("model.called", target=Target("usage_record", record_id))
    _log.info(
        "ai.embed",
        model=model,
        outcome=outcome,
        input_tokens=input_tokens,
        cost_usd=str(spent),
    )
    forget_spend()


async def embed(c: EmbedCall) -> EmbedResult:
    """Embed up to 64 texts: the per-call budget, the budget hierarchy, admission, then the
    provider; one usage record per provider call. `BudgetExceeded`, `BudgetExhausted`,
    `NotAdmitted` and `ProviderError` propagate (the caller retries or fails its work)."""
    if not 1 <= len(c.texts) <= MAX_TEXTS or any(
        not t or len(t) > MAX_TEXT_CHARS for t in c.texts
    ):
        raise EmbedTooLarge(f"1 to {MAX_TEXTS} texts of 1 to {MAX_TEXT_CHARS} characters")
    model = settings().embedding_model
    inputs_hash = hashlib.sha256("\x1f".join(c.texts).encode()).hexdigest()
    tokens = sum(estimate_tokens(t) for t in c.texts)
    estimate = embed_cost(tokens)
    with _tracer.start_as_current_span(
        "ai.embed",
        attributes={"ai.agent_id": c.attribution.agent_id, "ai.texts": len(c.texts)},
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            if estimate > c.budget_usd:
                await _record_embed(
                    c.attribution, model, 0, Decimal(0), "budget_refused", inputs_hash
                )
                raise BudgetExceeded(f"embedding would cost more than {c.budget_usd}")
            await check_budget(
                c.attribution.tenant, c.attribution.engagement_id, c.essential, estimate
            )
            admitted, wait = await admit(
                c.attribution.tenant, embedding_route(), model, c.work_class, c.essential, tokens
            )
            if not admitted:
                raise NotAdmitted(refusal_reason(c.work_class), wait)
            try:
                response = await embedder().embed(model, c.texts)
            except ProviderError:
                await _record_embed(
                    c.attribution, model, 0, Decimal(0), "provider_error", inputs_hash
                )
                raise
            if len(response.vectors) != len(c.texts) or any(
                len(v) != settings().embedding_dimensions for v in response.vectors
            ):
                await _record_embed(
                    c.attribution, model, response.input_tokens, Decimal(0), "invalid", inputs_hash
                )
                raise ProviderError("embedding response has the wrong shape")
            spent = embed_cost(response.input_tokens)
            await _record_embed(
                c.attribution, model, response.input_tokens, spent, "ok", inputs_hash
            )
        except Exception as exc:
            span.set_status(SpanStatus(StatusCode.ERROR, type(exc).__name__))
            raise
        span.set_attribute("ai.cost_usd", str(spent))
        return EmbedResult(response.vectors, model, spent)


def _parse[T: BaseModel](schema: type[T], body: str) -> tuple[T | None, str | None]:
    try:
        return schema.model_validate_json(body), None
    except ValidationError as exc:
        # Only where and what kind: never the model's text (it may echo client content).
        errors = [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return None, json.dumps(errors, default=str)


async def _spent_by_run(attribution: Attribution) -> Decimal:
    if attribution.agent_run_id is None:
        return Decimal(0)
    async with tenant_session(attribution.tenant) as session:
        total = (
            await session.execute(
                text(
                    "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records "
                    "WHERE agent_run_id = :run"
                ),
                {"run": attribution.agent_run_id},
            )
        ).scalar_one()
    return Decimal(str(total))


async def call[T: BaseModel](c: GatewayCall[T]) -> GatewayResult[T]:
    """One `ai.call` span per call (ADR-019, ADR-022): identifiers and outcome only, never the
    prompt, context or output. Each attempt is an `ai.attempt` event on it."""
    found = _check(c)
    # No purpose text or inputs hash on the span (free text; a hash of client context): those stay
    # in the usage record. Exceptions are recorded by class name only.
    with _tracer.start_as_current_span(
        "ai.call",
        attributes={
            "ai.prompt": found.ref,
            "ai.tier": c.tier,
            "ai.agent_id": c.attribution.agent_id,
        },
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            result = await _call(c, found)
        except NotAdmitted as waiting:  # waiting for capacity is not a failure
            span.set_attribute("ai.status", "not_admitted")
            span.set_attribute("ai.admission_reason", waiting.reason)
            raise
        except Exception as exc:
            span.set_status(SpanStatus(StatusCode.ERROR, type(exc).__name__))
            raise
        span.set_attribute("ai.status", result.status)
        span.set_attribute("ai.attempts", result.attempts)
        span.set_attribute("ai.cost_usd", str(result.cost_usd))
        span.set_attribute("ai.model", result.model)
        return result


def check_provider_limits() -> None:
    """Boot check: outside local and test, every model has provider limits. Without them its calls
    would never be admitted (fail closed), which should stop a deploy, not degrade it."""
    s = settings()
    if s.environment in ("local", "test"):
        return
    models = {
        model
        for entry in s.model_catalog.values()
        for route, model in entry.ids.items()
        if route in s.model_routes
    }
    missing = sorted(model for model in models if model not in s.provider_limits)
    if missing:
        raise RuntimeError(f"no provider limits for {', '.join(missing)} (provider_limits)")


# Evaluation mode (SPEC-005; TASK-020): the evaluation runner pins the tier an agent's calls use
# for one run. Tooling sets it; product code never does.
_evaluation_tier: ContextVar[Tier | None] = ContextVar("abacus_evaluation_tier", default=None)
_evaluation_route: ContextVar[Route | None] = ContextVar("abacus_evaluation_route", default=None)


@contextmanager
def evaluation(tier: Tier | None, route: Route | None = None) -> Generator[None]:
    """Run the block's model calls on `tier` and, if given, `route` (the evaluation runner's
    pinned tier and route, SPEC-010 AC-6). Evaluation calls aren't gated by eligibility."""
    token = _evaluation_tier.set(tier)
    route_token = _evaluation_route.set(route)
    try:
        yield
    finally:
        _evaluation_route.reset(route_token)
        _evaluation_tier.reset(token)


async def eligible(
    tenant: TenantContext,
    agent_id: str,
    route: Route,
    tier: Tier,
    model: str,
    prompt_version: str,
) -> bool:
    """Whether the latest finished full-suite evaluation run of `agent_id` on this tier and model,
    with its current prompt and suite version, passed on a real model (SPEC-005 AC-13). The
    prompt must be the agent's own (`_eval_suites`, generated from its spec), so a call can't
    borrow another agent's eligibility. Fails closed: an unknown agent, another prompt, or any
    error means no."""
    known = EVAL_SUITES.get(agent_id)
    if known is None or known[0] != prompt_version:
        return False
    try:
        async with tenant_session(tenant) as session:
            found = await session.scalar(
                text("SELECT eval_eligible(:agent, :route, :tier, :model, :prompt, :suite)"),
                {
                    "agent": agent_id,
                    "route": route,
                    "tier": tier,
                    "model": model,
                    "prompt": prompt_version,
                    "suite": known[1],
                },
            )
    except Exception as exc:
        _log.warning(
            "admission.eligibility_unavailable", agent_id=agent_id, error=type(exc).__name__
        )
        return False
    return bool(found)


def _candidate_routes(c: GatewayCall[BaseModel], excluded: frozenset[Route]) -> list[Route]:
    """The routes this call may try, in order (SPEC-010 §6): the evaluation run's pinned route;
    else `fake` when enabled (synthetic environments, D1), then the agent's own routes that are
    enabled with current parity (Q2). Routes refused for credentials this call are left out."""
    pinned = _evaluation_route.get()
    if pinned is not None:
        return [pinned] if pinned in settings().model_routes else []
    ordered = ["fake", *c.routes]
    seen: list[Route] = []
    for route in cast(list[Route], ordered):
        if route not in seen and route not in excluded and route_enabled(route):
            seen.append(route)
    return seen


async def _admitted(
    c: GatewayCall[BaseModel],
    tiers: tuple[Tier, ...],
    tokens: int,
    prompt_version: str,
    excluded: frozenset[Route] = frozenset(),
) -> tuple[Tier, Route, str]:
    """The first tier and route whose model admits this call (an `ai.admit` span), or
    `NotAdmitted`. ADR-072's order: background and batch work is deferred, never stepped down;
    interactive and time-sensitive work steps down to a cheaper tier the spec allows, after every
    route of the preferred tier (SPEC-010), then waits visibly."""
    tenant = c.attribution.tenant
    if c.work_class in ("background", "batch"):
        tiers = tiers[:1]
    routes = _candidate_routes(c, excluded)
    synthetic = settings().environment in SYNTHETIC_ENVIRONMENTS
    evaluating = _evaluation_route.get() is not None or _evaluation_tier.get() is not None
    with _tracer.start_as_current_span("ai.admit", attributes={"ai.work_class": c.work_class}):
        retry_after = 60
        for index, tier in enumerate(tiers):
            for route in routes:
                model = model_id(tier, route)
                if model is None:
                    continue
                # A cheaper tier needs a passing evaluation run (SPEC-005); outside synthetic
                # environments so does every real route (SPEC-010 AC-6, ADR-073).
                gated = index > 0 or (not synthetic and route != "fake" and not evaluating)
                if gated and not await eligible(
                    tenant, c.attribution.agent_id, route, tier, model, prompt_version
                ):
                    _log.info(
                        "admission.route_ineligible",
                        agent_id=c.attribution.agent_id,
                        route=route,
                        tier=tier,
                    )
                    continue
                admitted, wait = await admit(
                    tenant, route, model, c.work_class, c.essential, tokens
                )
                if admitted:
                    return tier, route, model
                retry_after = min(retry_after, wait)
    raise NotAdmitted(refusal_reason(c.work_class), retry_after)


def _next_route_exists(c: GatewayCall[BaseModel], tier: Tier, excluded: frozenset[Route]) -> bool:
    return any(model_id(tier, r) is not None for r in _candidate_routes(c, excluded))


async def _call[T: BaseModel](c: GatewayCall[T], found: Prompt) -> GatewayResult[T]:
    pinned = _evaluation_tier.get()
    tier = pinned or c.tier
    planned = _candidate_routes(cast(GatewayCall[BaseModel], c), frozenset())
    route: Route = planned[0] if planned else "fake"
    model = model_id(tier, route) or settings().model_catalog[tier].name
    user = c.context.render()
    inputs_hash = hashlib.sha256(f"{found.ref}\n{user}".encode()).hexdigest()
    spent = Decimal(0)
    earlier = await _spent_by_run(c.attribution)
    request = ModelRequest(model, found.text, user, c.max_output_tokens, found.ref)
    for attempt in (1, 2):
        estimate = cost(tier, estimate_tokens(request.system + request.user), c.max_output_tokens)
        if earlier + spent + estimate > c.budget_usd:
            await _record_usage(
                c.attribution,
                found=found,
                model=model,
                tier=tier,
                response=None,
                spent=Decimal(0),
                outcome="budget_refused",
                inputs_hash=inputs_hash,
                route=route,
            )
            if attempt == 1:
                raise BudgetExceeded(f"{found.ref} would cost more than {c.budget_usd}")
            return GatewayResult(
                "escalated", None, attempt - 1, spent, inputs_hash, model, found, route
            )
        # The budget hierarchy (ADR-069; SPEC-007): engagement, firm and platform levels.
        await check_budget(
            c.attribution.tenant, c.attribution.engagement_id, c.essential, estimate
        )
        # Admission before every attempt; only the first may step down to a cheaper tier.
        needed = estimate_tokens(request.system + request.user) + c.max_output_tokens
        # Evaluation mode never steps down: a run measures exactly the tier it pinned.
        tiers = (tier, *c.cheaper_tiers) if attempt == 1 and pinned is None else (tier,)
        excluded: set[Route] = set()
        while True:  # SPEC-010: a failed route hands the attempt to the next allowed route
            tier, route, model = await _admitted(
                cast(GatewayCall[BaseModel], c), tiers, needed, found.ref, frozenset(excluded)
            )
            request = replace(request, model=model)
            try:
                async with asyncio.timeout(c.timeout_seconds):
                    response = await route_provider(route).complete(request)
                break
            except (ProviderError, TimeoutError) as exc:
                error = exc if isinstance(exc, ProviderError) else ProviderError("timeout")
                wait = await _route_failed(c.attribution, route, model, error)
                billed = (
                    Decimal(0)
                    if error.rate_limited or error.auth
                    else cost(tier, estimate_tokens(request.system + request.user), 0)
                )
                # The provider may bill a call that failed or timed out: count its input, so
                # retries can't spend past the run's budget on calls recorded as free.
                spent += billed
                await _record_usage(
                    c.attribution,
                    found=found,
                    model=model,
                    tier=tier,
                    response=None,
                    spent=billed,
                    outcome="rate_limited" if error.rate_limited else "provider_error",
                    inputs_hash=inputs_hash,
                    route=route,
                )
                excluded.add(route)
                tiers = (tier,)
                if _next_route_exists(cast(GatewayCall[BaseModel], c), tier, frozenset(excluded)):
                    _failovers.add(1, {"route": route, "reason": _reason(error)})
                    _log.info("ai.failover", route=route, reason=_reason(error))
                    continue
                if error.rate_limited:
                    # Never retried here (SPEC-003 AC-12): the call waits for admission.
                    raise NotAdmitted(refusal_reason(c.work_class), wait) from None
                if isinstance(exc, TimeoutError):
                    raise ProviderError(f"{found.ref} timed out") from None
                raise error from None
        this_cost = cost(tier, response.input_tokens, response.output_tokens)
        spent += this_cost
        output, errors = _parse(c.output_schema, response.text)
        outcome: Outcome = "invalid" if output is None else ("ok" if attempt == 1 else "repaired")
        await _record_usage(
            c.attribution,
            found=found,
            model=model,
            tier=tier,
            response=response,
            spent=this_cost,
            outcome=outcome,
            inputs_hash=inputs_hash,
            route=route,
        )
        if output is not None:
            return GatewayResult(
                "ok" if attempt == 1 else "repaired",
                output,
                attempt,
                spent,
                inputs_hash,
                model,
                found,
                route,
            )
        # One repair: the same request plus where the output failed the schema.
        request = ModelRequest(
            model,
            found.text,
            f"{user}\n\n## repair\nYour previous reply did not match the required schema. "
            f"Errors: {errors}\nReply again with one valid JSON object only.",
            c.max_output_tokens,
            found.ref,
        )
    return GatewayResult("escalated", None, 2, spent, inputs_hash, model, found, route)


def _reason(error: ProviderError) -> str:
    return "rate_limited" if error.rate_limited else ("auth" if error.auth else "outage")


async def _route_failed(
    attribution: Attribution, route: Route, model: str, error: ProviderError
) -> int:
    """Block the route's model (rate limit: for the wait asked; outage: `outage_block_seconds`,
    SPEC-010 Q3) and return the wait. Credentials refused: no block, an alert."""
    if error.auth:
        _log.error("provider.auth_failed", route=route, model=model)
        return 0
    if error.rate_limited:
        asked = error.retry_after
        wait = 30 if asked is None or not math.isfinite(asked) else max(1, ceil(asked))
    else:
        wait = settings().outage_block_seconds
    wait = min(wait, 3600)
    try:
        await block(attribution.tenant, route, model, wait)
    except Exception as failed:  # the call still moves on: never back to this route now
        _log.warning("admission.block_failed", route=route, model=model, error=failed)
    return wait


__all__ = [
    "MAX_ROWS",
    "MODELS",
    "AssembledContext",
    "Attribution",
    "BudgetExceeded",
    "BudgetExhausted",
    "CallTooLarge",
    "ContextBuilder",
    "ContextTooLarge",
    "DatasetTooLarge",
    "EmbedCall",
    "EmbedResult",
    "EmbedTooLarge",
    "EmbeddingProvider",
    "EmbeddingResponse",
    "FakeEmbedder",
    "FakeModel",
    "GatewayCall",
    "GatewayRefused",
    "GatewayResult",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "NotAdmitted",
    "Prompt",
    "ProviderError",
    "Route",
    "Tier",
    "UnknownPrompt",
    "call",
    "check_provider_limits",
    "configure_embedder",
    "configure_provider",
    "configure_route",
    "cost",
    "eligible",
    "embed",
    "estimate_tokens",
    "evaluation",
    "model_id",
    "prompt",
    "registry",
    "sanitise_text",
]
