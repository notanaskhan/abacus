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
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from abacus.ai_gateway.context import (
    MAX_ROWS,
    AssembledContext,
    ContextBuilder,
    ContextTooLarge,
    DatasetTooLarge,
    estimate_tokens,
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
    provider,
)
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, uow

# Per million tokens (input, output), by tier. The fake model is priced like a small model so
# budgets and metering are exercised exactly as they will be.
MODELS: dict[Tier, tuple[str, Decimal, Decimal]] = {
    "small": ("fake-small", Decimal("0.80"), Decimal("4.00")),
    "medium": ("fake-medium", Decimal("3.00"), Decimal("15.00")),
    "large": ("fake-large", Decimal("15.00"), Decimal("75.00")),
}
_MILLION = Decimal(1_000_000)
_log = get_logger(__name__)

Outcome = Literal["ok", "invalid", "repaired", "budget_refused", "provider_error"]
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
    max_output_tokens: int = 1_000
    # Per provider call; exceeding it is a provider error (retryable by the caller).
    timeout_seconds: float = 60


@dataclass(frozen=True)
class GatewayResult[T: BaseModel]:
    status: Status
    output: T | None
    attempts: int
    cost_usd: Decimal
    inputs_hash: str
    model: str
    prompt: Prompt


def cost(tier: Tier, input_tokens: int, output_tokens: int) -> Decimal:
    _, per_in, per_out = MODELS[tier]
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
) -> None:
    record_id = uuid4()
    async with uow(attribution.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO usage_records (id, tenant_id, engagement_id, agent_id, "
                "agent_run_id, prompt_id, prompt_version, model, tier, input_tokens, "
                "output_tokens, cost_usd, outcome, inputs_hash) VALUES (:id, :tenant, "
                ":engagement, :agent, :run, :prompt_id, :prompt_version, :model, :tier, "
                ":input_tokens, :output_tokens, :cost, :outcome, :inputs_hash)"
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
            },
        )
        tx.record("model.called", target=Target("usage_record", record_id))
    _log.info(
        "ai.call",
        prompt=found.ref,
        model=model,
        tier=tier,
        outcome=outcome,
        inputs_hash=inputs_hash,
        input_tokens=response.input_tokens if response else 0,
        output_tokens=response.output_tokens if response else 0,
        cost_usd=str(spent),
    )


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
    found = _check(c)
    model = MODELS[c.tier][0]
    user = c.context.render()
    inputs_hash = hashlib.sha256(f"{found.ref}\n{user}".encode()).hexdigest()
    spent = Decimal(0)
    earlier = await _spent_by_run(c.attribution)
    request = ModelRequest(model, found.text, user, c.max_output_tokens, found.ref)
    for attempt in (1, 2):
        estimate = cost(
            c.tier, estimate_tokens(request.system + request.user), c.max_output_tokens
        )
        if earlier + spent + estimate > c.budget_usd:
            await _record_usage(
                c.attribution,
                found=found,
                model=model,
                tier=c.tier,
                response=None,
                spent=Decimal(0),
                outcome="budget_refused",
                inputs_hash=inputs_hash,
            )
            if attempt == 1:
                raise BudgetExceeded(f"{found.ref} would cost more than {c.budget_usd}")
            return GatewayResult("escalated", None, attempt - 1, spent, inputs_hash, model, found)
        try:
            async with asyncio.timeout(c.timeout_seconds):
                response = await provider().complete(request)
        except (ProviderError, TimeoutError) as exc:
            await _record_usage(
                c.attribution,
                found=found,
                model=model,
                tier=c.tier,
                response=None,
                spent=Decimal(0),
                outcome="provider_error",
                inputs_hash=inputs_hash,
            )
            if isinstance(exc, TimeoutError):
                raise ProviderError(f"{found.ref} timed out") from None
            raise
        this_cost = cost(c.tier, response.input_tokens, response.output_tokens)
        spent += this_cost
        output, errors = _parse(c.output_schema, response.text)
        outcome: Outcome = "invalid" if output is None else ("ok" if attempt == 1 else "repaired")
        await _record_usage(
            c.attribution,
            found=found,
            model=model,
            tier=c.tier,
            response=response,
            spent=this_cost,
            outcome=outcome,
            inputs_hash=inputs_hash,
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
    return GatewayResult("escalated", None, 2, spent, inputs_hash, model, found)


__all__ = [
    "MAX_ROWS",
    "MODELS",
    "AssembledContext",
    "Attribution",
    "BudgetExceeded",
    "ContextBuilder",
    "ContextTooLarge",
    "DatasetTooLarge",
    "FakeModel",
    "GatewayCall",
    "GatewayRefused",
    "GatewayResult",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "Prompt",
    "ProviderError",
    "Tier",
    "UnknownPrompt",
    "call",
    "configure_provider",
    "cost",
    "estimate_tokens",
    "prompt",
    "registry",
]
