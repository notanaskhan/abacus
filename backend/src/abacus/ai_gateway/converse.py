"""`converse()`: one gateway conversation turn with tool use (P-10-T19; ADR-234; SPEC-647 §3.1,
AC-G1 to AC-G7). PROTECTED. New file, beside `call()`, which stays byte-for-byte unchanged (AC-G6).

A `ConverseCall` is one model turn of a run step: the registered prompt as the instructions layer,
the system layers in ADR-234 §5's fixed order (instructions, tools, firm, engagement, examples),
the conversation so far, the tools the step may call, and either an output schema for the turn's
structured final answer or none (a tool-using turn). Every `call()` invariant holds per attempt:

1. **Refusals before any provider call.** A missing purpose, prompt, tier, budget or attribution
   (`GatewayRefused`); an unmasked TIN anywhere in the turn (ADR-167); TRI without both §7216
   consents (`consent_7216`, every route and firm, never rerouted; ADR-115); the platform or firm
   AI pause and every other data-boundary reason (`enforce_boundary`, re-checked each attempt, so
   a pause stops the next turn within the controls cache's 10 s); the run's budget
   (`BudgetExceeded` on the first attempt, `budget_refused` recorded); admission (`NotAdmitted`).
2. **One record per attempt.** Each attempt writes exactly one `usage_records` row (with the run's
   `step_id` and `session_id`, 0681) and one `model.called` audit event in its own unit of work.
   Inputs are logged by hash only: never the prompt, the turns or the output.
3. **Route failover** as `call()`: a provider error hands the attempt to the next allowed route;
   a firm that is not synthetic never fails over off a client-data route (ADR-113).
4. **Tool arguments are validated** against each tool's input model before anything executes:
   `converse()` returns validated `ToolCallRequest`s and never runs a tool itself (the harness,
   P-10-T21, does, under the tool registry's checks). An invalid argument or an unknown tool gets
   one repair turn carrying the failure (a code and a path, never the text); if the repair fails
   too, the turn is `escalated` and the run goes to `needs_input` with reason `escalated` (AC-G4).
5. **A structured final turn** validates against `output_schema`, with the same one repair, then
   `escalated`. With an `output_kind`, it is then settled against the output-check registry
   (P-09-T04): one repair with the check's code and path, then `unsupported`, shown as the
   Unsupported state and never as the output. Nothing streams (AC-G7): the result is whole.

`converse()` commits per attempt, so never call it inside a unit of work.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID, uuid4

from opentelemetry import trace
from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from abacus.ai_gateway import (
    MODELS,
    Attribution,
    BudgetExceeded,
    GatewayCall,
    GatewayRefused,
    _admitted,  # pyright: ignore[reportPrivateUsage] -- the gateway's own admission, one package
    _candidate_routes,  # pyright: ignore[reportPrivateUsage]  # the gateway's own admission, shared in-package
    _next_route_exists,  # pyright: ignore[reportPrivateUsage]  # the gateway's own admission, shared in-package
    _route_failed,  # pyright: ignore[reportPrivateUsage]  # the gateway's own admission, shared in-package
    _spent_by_run,  # pyright: ignore[reportPrivateUsage]  # the gateway's own admission, shared in-package
    barred_routes,
    cost,
    unfenced,
)
from abacus.ai_gateway.admission import NotAdmitted, refusal_reason
from abacus.ai_gateway.boundary import Basis, enforce_boundary, enforce_tri_consent
from abacus.ai_gateway.budgets import check_budget, forget_spend
from abacus.ai_gateway.context import AssembledContext, DataSubject, estimate_tokens
from abacus.ai_gateway.output_checks import settle
from abacus.ai_gateway.pii import part_with_tin
from abacus.ai_gateway.prompts import Prompt, UnknownPrompt, prompt
from abacus.ai_gateway.providers import (
    ContentBlock,
    ConverseMessage,
    ConverseRequest,
    ConverseResponse,
    ProviderError,
    SystemBlock,
    TextBlock,
    Tier,
    ToolChoice,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from abacus.ai_gateway.routes import route_converser
from abacus.kernel.access import AccessSubject, record_reads
from abacus.kernel.classification import classified
from abacus.kernel.config import Route, settings
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, uow
from abacus.kernel.work_class import WorkClass

_log = get_logger(__name__)
_tracer = trace.get_tracer(__name__)

# `unsupported` (P-09-T04): a structured final turn that failed its output check after the one
# repair; the surface shows the Unsupported state, never the output (P-09 §3.7).
ConverseStatus = Literal["ok", "repaired", "tool_use", "escalated", "unsupported"]
AttemptOutcome = Literal[
    "ok", "invalid", "repaired", "budget_refused", "provider_error", "rate_limited"
]
# Why a turn's output failed, as a code: the repair turn carries it with a path, never the text.
TurnFailure = Literal[
    "schema_invalid",
    "tool_unknown",
    "tool_arguments_invalid",
    "no_output",
    "refusal",
    "output_check",
]
REPAIRS = 1


class ConverseTool(BaseModel):
    """A tool the turn may call: the provider's view (`spec`) and the input model its arguments
    must satisfy. The description is the tool's registry prompt (ADR-049)."""

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    spec: Annotated[ToolSpec, classified("internal")]  # a registered tool's name and schema
    input_model: Annotated[type[BaseModel], classified("internal")]  # the arguments' model


@dataclass(frozen=True)
class ConverseCall[T: BaseModel]:
    purpose: str
    prompt: str  # the instructions layer: a registered prompt `id@vN`
    tier: Tier
    budget_usd: Decimal  # the run's budget: earlier attempts of the same run count against it
    attribution: Attribution
    work_class: WorkClass
    essential: bool
    routes: tuple[Route, ...]
    messages: tuple[ConverseMessage, ...]
    # ADR-234 §5's later layers in order (tools, firm, engagement, examples); client content in
    # them is already inside `<untrusted>` blocks (ADR-052).
    layers: tuple[SystemBlock, ...] = ()
    tools: tuple[ConverseTool, ...] = ()
    tool_choice: ToolChoice = "auto"
    # The structured final turn's schema; None for a turn expected to call tools.
    output_schema: type[T] | None = None
    # P-09-T04: the output-check kind the structured final turn is settled against
    # (`ai_gateway.output_checks`, e.g. `agent_blocks`). An unregistered kind fails closed.
    output_kind: str | None = None
    # §7216 (C19): whose tax return information the turn carries.
    data_subjects: tuple[DataSubject, ...] = ()
    # Evidence versions in the turn, for the identifier-only access events (Q-02-T20).
    sources: tuple[UUID, ...] = ()
    step_id: UUID | None = None
    session_id: UUID | None = None
    max_output_tokens: int = 2_000
    timeout_seconds: float = 90
    cheaper_tiers: tuple[Tier, ...] = ()


@dataclass(frozen=True)
class ToolCallRequest:
    """A tool call whose arguments validated against the tool's input model. Nothing has run."""

    tool_use_id: str
    name: str
    arguments: BaseModel


@dataclass(frozen=True)
class ConverseResult[T: BaseModel]:
    status: ConverseStatus
    output: T | None
    tool_calls: tuple[ToolCallRequest, ...]
    attempts: int
    cost_usd: Decimal
    inputs_hash: str
    model: str
    prompt: Prompt
    route: Route
    # `escalated`: the last failure's code and path; the run goes to needs_input (`escalated`).
    failure: TurnFailure | None = None
    failure_where: str | None = None
    response: ConverseResponse | None = field(default=None, repr=False)


def _check(c: ConverseCall[BaseModel]) -> Prompt:
    if not c.purpose.strip():
        raise GatewayRefused("a call declares its purpose")
    if c.budget_usd <= 0:
        raise GatewayRefused("a call declares a positive budget")
    if c.tier not in MODELS:
        raise GatewayRefused("unknown tier")
    if not c.attribution.agent_id:
        raise GatewayRefused("a call is attributed to a firm and an agent")
    if not c.messages or c.messages[-1].role != "user":
        raise GatewayRefused("a turn ends on the user's message")
    schema = cast(object, c.output_schema)
    if schema is not None and not (isinstance(schema, type) and issubclass(schema, BaseModel)):
        raise GatewayRefused("an output schema is a Pydantic model")
    names = [t.spec.name for t in c.tools]
    if len(set(names)) != len(names):
        raise GatewayRefused("a tool is offered once")
    try:
        return prompt(c.prompt)
    except UnknownPrompt:
        raise GatewayRefused(f"prompt {c.prompt} is not registered") from None


def _block_text(block: ContentBlock) -> str:
    if isinstance(block, TextBlock):
        return block.text
    if isinstance(block, ToolUseBlock):
        return f"tool_use {block.name} {json.dumps(dict(block.input), sort_keys=True)}"
    if isinstance(block, ToolResultBlock):
        return f"tool_result {block.tool_use_id} {block.content}"
    return f"document {block.title or ''}"


def _turn_text(c: ConverseCall[BaseModel]) -> str:
    """Everything the turn sends, as one string: for the TIN check, the size estimate and the
    inputs hash (logged by hash only)."""
    parts = [b.text for b in c.layers]
    parts += [t.spec.description for t in c.tools]
    for m in c.messages:
        parts += [f"{m.role}: {_block_text(b)}" for b in m.content]
    return "\n".join(parts)


async def _record(
    c: ConverseCall[BaseModel],
    *,
    found: Prompt,
    model: str,
    tier: Tier,
    response: ConverseResponse | None,
    spent: Decimal,
    outcome: AttemptOutcome,
    inputs_hash: str,
    route: Route,
    basis: Basis | None,
) -> None:
    """AC-G5: one usage row and one `model.called` event, in their own unit of work."""
    record_id = uuid4()
    a = c.attribution
    async with uow(a.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO usage_records (id, tenant_id, engagement_id, agent_id, "
                "agent_run_id, prompt_id, prompt_version, model, tier, input_tokens, "
                "output_tokens, cost_usd, outcome, inputs_hash, route, boundary_basis, "
                "terms_version, step_id, session_id) VALUES (:id, :tenant, :engagement, "
                ":agent, :run, :prompt_id, :prompt_version, :model, :tier, :input_tokens, "
                ":output_tokens, :cost, :outcome, :inputs_hash, :route, :basis, "
                ":terms_version, :step, :session)"
            ),
            {
                "id": record_id,
                "tenant": a.tenant.tenant_id,
                "engagement": a.engagement_id,
                "agent": a.agent_id,
                "run": a.agent_run_id,
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
                "basis": basis.basis if basis else None,
                "terms_version": basis.terms_version if basis else None,
                "step": c.step_id,
                "session": c.session_id,
            },
        )
        tx.record("model.called", target=Target("usage_record", record_id))
    _log.info(
        "ai.converse",
        prompt=found.ref,
        route=route,
        model=model,
        tier=tier,
        outcome=outcome,
        inputs_hash=inputs_hash,
        cost_usd=str(spent),
    )
    forget_spend()


async def _record_reads(c: ConverseCall[BaseModel], consents: tuple[UUID, ...]) -> None:
    """Identifier-only access events, as `call()` writes them: one `model_context.built` per
    evidence version in the turn (Q-02-T20) and one `tri.agent_read` per taxpayer and covering
    consent (C19)."""
    a = c.attribution
    if c.sources:
        await record_reads(
            a.tenant,
            "model_context.built",
            [
                AccessSubject("evidence_version", s, engagement_id=a.engagement_id)
                for s in c.sources
            ],
            run_id=a.agent_run_id,
        )
    if c.data_subjects:
        await record_reads(
            a.tenant,
            "tri.agent_read",
            [
                *(
                    AccessSubject(
                        "client_entity",
                        s.entity_id,
                        engagement_id=a.engagement_id,
                        tax_year=s.tax_year,
                    )
                    for s in c.data_subjects
                    if s.entity_id is not None
                ),
                *(AccessSubject("consent", k, engagement_id=a.engagement_id) for k in consents),
            ],
            run_id=a.agent_run_id,
        )


def _turn_cost(tier: Tier, response: ConverseResponse) -> Decimal:
    """Cached input reads and writes are priced as plain input until the catalog prices them
    apart (never under-counted against the budget)."""
    tokens_in = response.input_tokens + response.cache_read_tokens + response.cache_write_tokens
    return cost(tier, tokens_in, response.output_tokens)


def _validated_tools(
    c: ConverseCall[BaseModel], uses: tuple[ToolUseBlock, ...]
) -> tuple[tuple[ToolCallRequest, ...], TurnFailure | None, str | None]:
    offered: Mapping[str, ConverseTool] = {t.spec.name: t for t in c.tools}
    calls: list[ToolCallRequest] = []
    for use in uses:
        tool = offered.get(use.name)
        if tool is None:
            return (), "tool_unknown", use.name
        try:
            arguments = tool.input_model.model_validate(dict(use.input))
        except ValidationError as exc:
            where = ".".join(str(p) for p in exc.errors()[0]["loc"]) if exc.errors() else ""
            return (), "tool_arguments_invalid", f"{use.name}.{where}".rstrip(".")
        calls.append(ToolCallRequest(use.id, use.name, arguments))
    return tuple(calls), None, None


def _parsed[T: BaseModel](
    schema: type[T], body: str
) -> tuple[T | None, TurnFailure | None, str | None]:
    try:
        return schema.model_validate_json(unfenced(body)), None, None
    except ValidationError as exc:
        errors = exc.errors()
        where = ".".join(str(p) for p in errors[0]["loc"]) if errors else ""
        return None, "schema_invalid", where


def _repair_turn(failure: TurnFailure, where: str | None) -> ConverseMessage:
    """The one repair: the failure's code and path, never the offending text (P-09 §3.7)."""
    return ConverseMessage(
        "user",
        (
            TextBlock(
                f"## repair\nYour previous turn failed the gateway's check: {failure}"
                f" at {where or '(root)'}. Answer again, using only the tools offered with "
                "arguments that match their schemas, or one valid JSON object as the answer."
            ),
        ),
    )


async def converse[T: BaseModel](c: ConverseCall[T]) -> ConverseResult[T]:
    """One `ai.converse` span per call: identifiers and outcome only."""
    found = _check(cast(ConverseCall[BaseModel], c))
    with _tracer.start_as_current_span(
        "ai.converse",
        attributes={
            "ai.prompt": found.ref,
            "ai.tier": c.tier,
            "ai.agent_id": c.attribution.agent_id,
        },
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        result = await _converse(c, found)
        span.set_attribute("ai.status", result.status)
        span.set_attribute("ai.attempts", result.attempts)
        span.set_attribute("ai.cost_usd", str(result.cost_usd))
        return result


async def _converse[T: BaseModel](c: ConverseCall[T], found: Prompt) -> ConverseResult[T]:
    # Admission and routing read only `routes`, `work_class`, `essential` and `attribution`, which
    # a ConverseCall has too: the gateway's own admission, not a second copy.
    gc = cast("GatewayCall[BaseModel]", c)
    tier: Tier = c.tier
    planned = _candidate_routes(gc, frozenset())
    route: Route = planned[0] if planned else "fake"
    model = settings().model_catalog[tier].name
    sent = _turn_text(cast(ConverseCall[BaseModel], c))
    # ADR-167 §2: an unmasked TIN form refuses before budget, admission, record or provider.
    if part_with_tin(f"{found.text}\n{sent}", AssembledContext(())) is not None:
        raise GatewayRefused("an unmasked TIN is in the turn")
    # AC-G1: TRI without both §7216 consents refuses first, on every route, never rerouted.
    await enforce_tri_consent(c.attribution.tenant, route, found.ref, c.data_subjects)
    inputs_hash = hashlib.sha256(f"{found.ref}\n{sent}".encode()).hexdigest()
    earlier = await _spent_by_run(c.attribution)
    spent = Decimal(0)
    temperature = settings().model_catalog[tier].temperature
    system = (SystemBlock(found.text, cache=True), *c.layers)
    messages = c.messages
    barred = await barred_routes(c.attribution.tenant)
    if barred and planned and not _candidate_routes(gc, barred):
        await enforce_boundary(
            c.attribution.tenant,
            planned[0],
            found.ref,
            agent_id=c.attribution.agent_id,
            engagement_id=c.attribution.engagement_id,
            subjects=c.data_subjects,
        )
    basis: Basis | None = None
    read_recorded = False
    failure: TurnFailure | None = None
    where: str | None = None
    last: ConverseResponse | None = None
    attempt = 0
    for attempt in range(1, REPAIRS + 2):
        estimate = cost(tier, estimate_tokens(f"{found.text}\n{sent}"), c.max_output_tokens)
        if earlier + spent + estimate > c.budget_usd:  # AC-G2: no provider call
            await _record(
                cast(ConverseCall[BaseModel], c),
                found=found,
                model=model,
                tier=tier,
                response=None,
                spent=Decimal(0),
                outcome="budget_refused",
                inputs_hash=inputs_hash,
                route=route,
                basis=basis,
            )
            if attempt == 1:
                raise BudgetExceeded(f"{found.ref} would cost more than {c.budget_usd}")
            return ConverseResult(
                "escalated", None, (), attempt - 1, spent, inputs_hash, model, found, route,
                failure, where, last,
            )  # fmt: skip
        await check_budget(
            c.attribution.tenant, c.attribution.engagement_id, c.essential, estimate
        )
        needed: int = estimate_tokens(f"{found.text}\n{sent}") + int(c.max_output_tokens)
        tiers = (tier, *c.cheaper_tiers) if attempt == 1 else (tier,)
        excluded: set[Route] = set(barred)
        while True:
            tier, route, model = await _admitted(
                gc,
                tiers,
                needed,
                found.ref,
                frozenset(excluded),
            )
            request = ConverseRequest(
                model=model,
                system_blocks=system,
                messages=messages,
                max_output_tokens=c.max_output_tokens,
                prompt_ref=found.ref,
                tools=tuple(t.spec for t in c.tools),
                tool_choice=c.tool_choice,
                temperature=temperature,
            )
            try:
                consents = await enforce_tri_consent(  # fresh each attempt
                    c.attribution.tenant, route, found.ref, c.data_subjects
                )
                basis = await enforce_boundary(  # AC-G3: the AI pause, re-read each attempt
                    c.attribution.tenant,
                    route,
                    found.ref,
                    agent_id=c.attribution.agent_id,
                    engagement_id=c.attribution.engagement_id,
                )
                if not read_recorded:  # Q-02-T20, C19: once per call, as the content leaves
                    await _record_reads(cast(ConverseCall[BaseModel], c), consents)
                    read_recorded = True
                response = await asyncio.wait_for(
                    route_converser(route).converse(request), c.timeout_seconds
                )
                break
            except (ProviderError, TimeoutError) as exc:
                error = exc if isinstance(exc, ProviderError) else ProviderError("timeout")
                wait = await _route_failed(c.attribution, route, model, error)
                billed = (
                    Decimal(0)
                    if error.rate_limited or error.auth
                    else cost(tier, estimate_tokens(f"{found.text}\n{sent}"), 0)
                )
                spent += billed
                await _record(
                    cast(ConverseCall[BaseModel], c),
                    found=found,
                    model=model,
                    tier=tier,
                    response=None,
                    spent=billed,
                    outcome="rate_limited" if error.rate_limited else "provider_error",
                    inputs_hash=inputs_hash,
                    route=route,
                    basis=basis,
                )
                excluded.add(route)
                tiers = (tier,)
                if _next_route_exists(gc, tier, frozenset(excluded)):
                    _log.info("ai.failover", route=route)
                    continue
                if error.rate_limited:
                    raise NotAdmitted(refusal_reason(c.work_class), wait) from None
                if isinstance(exc, TimeoutError):
                    raise ProviderError(f"{found.ref} timed out") from None
                raise error from None
        last = response
        this_cost = _turn_cost(tier, response)
        spent += this_cost
        calls: tuple[ToolCallRequest, ...] = ()
        output: T | None = None
        unsupported = False
        if response.stop_reason == "refusal":
            failure, where = "refusal", None
        elif response.tool_uses:
            calls, failure, where = _validated_tools(
                cast(ConverseCall[BaseModel], c), response.tool_uses
            )
        elif c.output_schema is not None:
            output, failure, where = _parsed(c.output_schema, response.text)
            if output is not None and c.output_kind is not None:
                # P-09-T04 (DE-3, DE-5, DE-6): the owner's check on the structured final turn,
                # one repair with its code and path, then Unsupported. `call()` never runs it.
                settled = settle(c.output_kind, output, attempt - 1)
                if settled.outcome != "passed":
                    check = settled.failure
                    failure = "output_check"
                    where = None if check is None else f"{check.code}@{check.where}"
                    output = None
                    if settled.outcome == "unsupported":
                        unsupported = True
        elif not response.text.strip():
            failure, where = "no_output", None
        else:
            failure = None
        outcome: AttemptOutcome = (
            "invalid" if failure is not None else ("ok" if attempt == 1 else "repaired")
        )
        await _record(
            cast(ConverseCall[BaseModel], c),
            found=found,
            model=model,
            tier=tier,
            response=response,
            spent=this_cost,
            outcome=outcome,
            inputs_hash=inputs_hash,
            route=route,
            basis=basis,
        )
        if failure is None:
            status: ConverseStatus = (
                "tool_use" if calls else ("ok" if attempt == 1 else "repaired")
            )
            return ConverseResult(
                status, output, calls, attempt, spent, inputs_hash, model, found, route,
                None, None, response,
            )  # fmt: skip
        if unsupported:
            return ConverseResult(
                "unsupported", None, (), attempt, spent, inputs_hash, model, found, route,
                failure, where, response,
            )  # fmt: skip
        if failure == "refusal":
            break  # a refusal is not repaired: the run goes to a person
        # AC-G4: one repair with the failure's code and path; the assistant's turn is replayed
        # so the model sees what it sent.
        messages = (
            *messages,
            ConverseMessage("assistant", response.content_blocks),
            *(
                (
                    ConverseMessage(
                        "user",
                        tuple(
                            ToolResultBlock(u.id, f"rejected: {failure}", is_error=True)
                            for u in response.tool_uses
                        ),
                    ),
                )
                if response.tool_uses
                else ()
            ),
            _repair_turn(failure, where),
        )
        sent = _turn_text(replace(cast(ConverseCall[BaseModel], c), messages=messages))
    final: ConverseStatus = "unsupported" if failure == "output_check" else "escalated"
    return ConverseResult(
        final, None, (), attempt, spent, inputs_hash, model, found, route,
        failure, where, last,
    )  # fmt: skip


__all__ = [
    "REPAIRS",
    "ConverseCall",
    "ConverseResult",
    "ConverseStatus",
    "ConverseTool",
    "ToolCallRequest",
    "TurnFailure",
    "converse",
]
