"""C17 v1's runtime: calling one registered tool for one run step (P-10-T22; SPEC-647 AC-R2 to
AC-R7; ADR-233, ADR-049, ADR-050, ADR-052, ADR-167). PROTECTED.
Contract: `docs/contracts/tool-registry.md` §5 to §8 (frozen at v1 with this task).

`call_tool(agent, call)` is the only way a tool's handler runs. The harness (P-10-T25) calls it
from its `call_tool` activity with the run's `AgentContext`, which `identity` issued from the run
row, never from a workflow input. In order, before the handler:

1. the tool is registered (`tool_not_registered`), and its arguments validate against its input
   model (`invalid_arguments`; nothing runs, the harness repairs once then escalates, AC-G4);
2. every target (the engagements and clients the arguments name; the run's own engagement when
   they name none) is inside the run's pinned `client_scope` (`out_of_scope`: AC-R2). Nothing
   about the refused client is recorded or answered: the refusal carries no id, count or name;
3. `authorise(agent, tool.action, engagement)` per target: `task_scope`, the initiator's live
   rights, ethical walls and the matrix (ADR-025, ADR-026). A wall, a missing relationship or
   another tenant answers `not_visible` (404 semantics, no count or name: AC-R3); a role the
   agent or its initiator lacks answers `not_permitted`;
4. a `tri` tool's taxpayers each hold `use` and `ai_disclosure` in force for the year
   (`consent_required`, raised by C19's tool-layer gate before any query runs: AC-R4). The gate
   records one `tri.tool_read` access event per taxpayer and covering consent;
5. an `approved_write` carries an approval grant that `identity.consume_grant` accepts for this
   step's payload (`no_grant`);
6. a `propose` or `approved_write` claims its idempotency key `(run_id, step_seq, attempt)` in
   `agent_tool_calls` (migration 0750): a retry of the same arguments gets the stored answer and
   the effect doesn't run again; other arguments under the same key answer
   `idempotency_key_reused` (AC-R7).

After the handler: a row list longer than the tool's `max_rows` is refused (`row_limit`: the tool
paginates, AC-R6); every text value is scrubbed of unmasked TINs (no full TIN is ever in a result,
AC-R4); a `restricted` or `tri` read writes identifier-only access events before the result is
handed over (Q-02-T20). The outcome carries `records_read`; the harness writes it to the step
with the step's state (P-10-T25), so a read writes no audit event (SPEC-647 §4.5). The model
reads the result through `for_model`, which puts the tool's `untrusted` fields in `<untrusted>`
blocks (AC-R5).

A refusal or error is an outcome, never an exception: the model reads the code and nothing else.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol, cast, runtime_checkable
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text

from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.tin_patterns import scrub_tins
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.tools.registry import (
    AgentTool,
    ToolNotRegistered,
    ToolRefusal,
    row_fields,
    tool,
)
from abacus.modules.engagements.api import client_of
from abacus.modules.identity.api import (
    AgentContext,
    Forbidden,
    Resource,
    authorise,
    consume_grant,
    engagement_resource,
)
from abacus.modules.organisations.api import (
    TriConsentRequired,
    TriSubject,
    require_tri_consent,
)

_log = get_logger(__name__)

# What a call can answer besides a result. The refusals are C17 §5's; the errors are the runtime's.
ToolError = Literal[
    "tool_not_registered",
    "invalid_arguments",
    "not_permitted",
    "idempotency_key_reused",
    "tool_failed",
]
ToolCode = Literal[
    "consent_required",
    "not_visible",
    "out_of_scope",
    "row_limit",
    "stale_source",
    "no_grant",
    "tool_not_registered",
    "invalid_arguments",
    "not_permitted",
    "idempotency_key_reused",
    "tool_failed",
]
REFUSALS: Final[frozenset[str]] = frozenset(ToolRefusal.__args__)
ERRORS: Final[frozenset[str]] = frozenset(ToolError.__args__)
_WRITES: Final = frozenset({"propose", "approved_write"})
# Layers a refusal answers as if the record did not exist (ADR-026): no count, no name.
_HIDDEN: Final = frozenset({"tenancy", "wall", "relationship", "client_scope"})

# Q-02-T20: an agent's read of Restricted content through a tool. TRI reads are C19's
# `tri.tool_read`, written by `require_tri_consent`.
RESTRICTED_READ: Final = "agent_tool.restricted_read"
register_access_kind(RESTRICTED_READ, ["restricted"])


class ToolCallIn(BaseModel):
    """One model-requested tool call, as the harness hands it over (C17 v1, frozen)."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    step_seq: int = Field(ge=1)
    attempt: int = Field(ge=1)
    name: str = Field(max_length=80)
    arguments: dict[str, object] = Field(default_factory=dict)
    # An approved_write's grant, issued by P-04 from a person's approval.
    grant_id: UUID | None = None


class ToolOutcome(BaseModel):
    """What a call answers (C17 v1, frozen). Exactly one of `result` and `code` is set. A refusal
    carries no detail about the refused record: the model reads the code alone."""

    name: str
    ok: bool
    code: ToolCode | None = None
    result: dict[str, object] | None = None
    records_read: int = Field(default=0, ge=0)
    # Restricted or TRI content was read: the harness keeps it out of logs and summaries.
    restricted: bool = False
    replayed: bool = False
    active_ms: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class ToolTargets:
    """The records a call reaches, for scope pinning, authorisation and §7216. Code resolves them
    from the arguments; the model never names its own scope."""

    engagement_ids: tuple[UUID, ...] = ()
    client_ids: tuple[UUID, ...] = ()
    tri_subjects: tuple[TriSubject, ...] = ()


@runtime_checkable
class TargetsArguments(Protocol):
    """An input model that knows its own targets (a tool whose records sit under another id)."""

    def tool_targets(self, agent: AgentContext) -> ToolTargets: ...


def default_targets(args: BaseModel, agent: AgentContext) -> ToolTargets:
    """Targets read from the conventional field names: `engagement_id`/`engagement_ids`,
    `client_id`, and for TRI `client_entity_id`/`client_entity_ids` with `tax_year`. With no
    engagement named, the run's own engagement is the target."""
    if isinstance(args, TargetsArguments):
        return args.tool_targets(agent)
    values = args.model_dump()
    engagements = _ids(values.get("engagement_ids")) + _ids(values.get("engagement_id"))
    if not engagements and agent.engagement_id is not None:
        engagements = (agent.engagement_id,)
    clients = _ids(values.get("client_id"))
    year = values.get("tax_year")
    entities = _ids(values.get("client_entity_ids")) + _ids(values.get("client_entity_id"))
    subjects = tuple(
        TriSubject(e, year if isinstance(year, int) else None) for e in dict.fromkeys(entities)
    )
    return ToolTargets(tuple(dict.fromkeys(engagements)), clients, subjects)


def _ids(value: object) -> tuple[UUID, ...]:
    if value is None:
        return ()
    items: Sequence[object] = (
        cast(Sequence[object], value) if isinstance(value, (list, tuple)) else (value,)
    )
    return tuple(i if isinstance(i, UUID) else UUID(str(i)) for i in items)


def args_hash(name: str, arguments: Mapping[str, object]) -> str:
    """The SHA-256 of a call's tool and canonical arguments (`agent_run_steps.args_hash`)."""
    canonical = json.dumps({"tool": name, "args": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


_CONSUMER: Final = UUID("6f1c2e0a-7d4b-5c3e-9a21-0c17a0b1c2d3")


def consumer_ref(call: ToolCallIn) -> UUID:
    """The grant's consumer for one step: the same for every retry of `(run, step, attempt)`, so
    `consume_grant` lets the retry through and refuses any other effect."""
    return uuid5(_CONSUMER, f"{call.run_id}:{call.step_seq}:{call.attempt}")


def _refused(name: str, code: str, started: float) -> ToolOutcome:
    return ToolOutcome(name=name, ok=False, code=cast(ToolCode, code), active_ms=_ms(started))


def _ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


_PINNED = text("SELECT client_scope FROM agent_runs WHERE id = :run")


async def pinned_scope(agent: AgentContext) -> frozenset[UUID]:
    """The run's `client_scope`, pinned at plan approval (INV-3). Unpinned, an engagement run is
    pinned to its engagement's client; a firm-level run reaches no client."""
    async with tenant_session(agent.tenant) as session:
        row = (await session.execute(_PINNED, {"run": agent.agent_run_id})).first()
    if row is not None and row.client_scope:
        return frozenset(cast(list[UUID], row.client_scope))
    if agent.engagement_id is None:
        return frozenset()
    client = await client_of(agent.tenant, agent.engagement_id)
    return frozenset({client}) if client is not None else frozenset()


async def _scope_and_rights(
    agent: AgentContext, the_tool: AgentTool, targets: ToolTargets
) -> str | None:
    """Steps 2 and 3: the refusal code, or None when every target is in scope and allowed."""
    pinned = await pinned_scope(agent)
    resources: list[Resource] = []
    for engagement_id in targets.engagement_ids:
        try:
            resource = await engagement_resource(agent.tenant, engagement_id)
        except NotFound:
            return "not_visible"
        client = resource.client_id or await client_of(agent.tenant, engagement_id)
        if client is None:
            return "not_visible"
        if client not in pinned:
            return "out_of_scope"
        resources.append(resource)
    for client in targets.client_ids:
        if client not in pinned:
            return "out_of_scope"
        resources.append(Resource.client(agent.tenant_id, client))
    if not resources:
        resources.append(Resource.firm(agent.tenant_id))
    for resource in resources:
        try:
            await authorise(agent, the_tool.action, resource)
        except Forbidden as denied:
            return "not_visible" if denied.layer in _HIDDEN else "not_permitted"
    return None


def _scrub(value: object) -> object:
    """Every text value with unmasked TINs replaced by their masks (AC-R4)."""
    if isinstance(value, str):
        return scrub_tins(value)
    if isinstance(value, Mapping):
        return {str(k): _scrub(v) for k, v in cast(Mapping[object, object], value).items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in cast(Sequence[object], value)]
    return value


def _row_count(the_tool: AgentTool, output: BaseModel) -> tuple[int, bool]:
    """The rows read, and whether any row list is over the tool's limit. A tool without row lists
    read one record."""
    lists = [getattr(output, name) for name in row_fields(the_tool.output_model)]
    if not lists:
        return 1, False
    return sum(len(rows) for rows in lists), any(len(rows) > the_tool.max_rows for rows in lists)


_CLAIM = text(
    "INSERT INTO agent_tool_calls (tenant_id, run_id, step_seq, attempt, tool_name, args_hash) "
    "VALUES (:tenant, :run, :seq, :attempt, :tool, :sha) "
    "ON CONFLICT (tenant_id, run_id, step_seq, attempt) DO NOTHING RETURNING id"
)
_FIND = text(
    "SELECT id, tool_name, args_hash, state, result FROM agent_tool_calls "
    "WHERE run_id = :run AND step_seq = :seq AND attempt = :attempt"
)
_DONE = text(
    "UPDATE agent_tool_calls SET state = 'done', result = CAST(:result AS jsonb), "
    "completed_at = clock_timestamp() WHERE id = :id AND state = 'claimed'"
)
_RELEASE = text("DELETE FROM agent_tool_calls WHERE id = :id AND state = 'claimed'")


@dataclass
class _Claim:
    id: UUID | None = None
    stored: dict[str, object] | None = None
    code: str | None = None


async def _claim(agent: AgentContext, call: ToolCallIn, sha: str) -> _Claim:
    """Step 6: claim the key in its own unit of work, or answer the stored result of the call that
    holds it. The handler's own effect runs after, in the owning module's unit of work."""
    params = {
        "tenant": agent.tenant_id,
        "run": call.run_id,
        "seq": call.step_seq,
        "attempt": call.attempt,
        "tool": call.name,
        "sha": sha,
    }
    async with uow(agent.tenant) as tx:
        claimed = (await tx.session.execute(_CLAIM, params)).first()
        if claimed is not None:
            tx.record(
                "agent_tool.call_claimed",
                target=Target("agent_run", call.run_id),
                after=Ref(tool_call=cast(UUID, claimed.id), step_seq=call.step_seq),
                scope=Scope(engagement_id=agent.engagement_id),
            )
            return _Claim(id=cast(UUID, claimed.id))
        found = (await tx.session.execute(_FIND, params)).first()
    if found is None:  # the holder released it between the two statements: the harness retries
        return _Claim(code="tool_failed")
    if found.tool_name != call.name or found.args_hash != sha:
        return _Claim(code="idempotency_key_reused")
    if found.state != "done":
        return _Claim(code="tool_failed")  # the first is still running; the harness retries
    return _Claim(stored=cast(dict[str, object], found.result))


async def _settle(
    agent: AgentContext, call: ToolCallIn, claim_id: UUID, result: dict[str, object] | None
) -> None:
    """Record the answer (`done`), or release the claim when the effect failed before it
    committed, so the retry can claim again."""
    async with uow(agent.tenant) as tx:
        if result is None:
            await tx.session.execute(_RELEASE, {"id": claim_id})
            kind = "agent_tool.call_released"
        else:
            await tx.session.execute(
                _DONE, {"id": claim_id, "result": json.dumps(result, default=str)}
            )
            kind = "agent_tool.call_completed"
        tx.record(
            kind,
            target=Target("agent_run", call.run_id),
            after=Ref(tool_call=claim_id, step_seq=call.step_seq),
            scope=Scope(engagement_id=agent.engagement_id),
        )


async def _record(
    agent: AgentContext, the_tool: AgentTool, call: ToolCallIn, targets: ToolTargets
) -> None:
    """Identifier-only access events for a Restricted read, before the result is handed over
    (TRI's were written by C19's gate)."""
    if the_tool.data_class != "restricted" or the_tool.kind not in ("read", "compute"):
        return
    subjects = [
        AccessSubject("engagement", e, engagement_id=e) for e in targets.engagement_ids
    ] or [AccessSubject("client", c, client_id=c) for c in targets.client_ids]
    await record_reads(agent.tenant, RESTRICTED_READ, subjects, run_id=call.run_id)


async def call_tool(agent: AgentContext, call: ToolCallIn) -> ToolOutcome:
    """Run one tool call for `agent`'s run under C17's rules (module docstring)."""
    started = time.monotonic()
    if call.run_id != agent.agent_run_id:
        return _refused(call.name, "not_permitted", started)
    try:
        the_tool = tool(call.name)
    except ToolNotRegistered:
        return _refused(call.name, "tool_not_registered", started)
    try:
        args = the_tool.input_model.model_validate(call.arguments)
    except ValidationError:
        return _refused(call.name, "invalid_arguments", started)
    try:
        targets = default_targets(args, agent)
    except (TypeError, ValueError):
        return _refused(call.name, "invalid_arguments", started)
    refusal = await _scope_and_rights(agent, the_tool, targets)
    if refusal is not None:
        return _refused(call.name, refusal, started)
    engagement = targets.engagement_ids[0] if targets.engagement_ids else agent.engagement_id
    if the_tool.data_class == "tri":
        if not targets.tri_subjects:
            return _refused(call.name, "consent_required", started)
        try:
            await require_tri_consent(
                agent.tenant,
                list(targets.tri_subjects),
                run_id=call.run_id,
                engagement_id=engagement,
            )
        except TriConsentRequired:
            return _refused(call.name, "consent_required", started)
    sha = args_hash(call.name, args.model_dump(mode="json"))
    if the_tool.kind == "approved_write" and (
        call.grant_id is None
        or not await consume_grant(agent.tenant_id, call.grant_id, consumer_ref(call), sha)
    ):
        return _refused(call.name, "no_grant", started)
    claim = _Claim()
    if the_tool.kind in _WRITES:
        claim = await _claim(agent, call, sha)
        if claim.code is not None:
            return _refused(call.name, claim.code, started)
        if claim.stored is not None:
            return ToolOutcome(
                name=call.name, ok=True, result=claim.stored, replayed=True, active_ms=_ms(started)
            )
    try:
        output = await the_tool.handler(agent, args)
        if not isinstance(output, the_tool.output_model):
            raise TypeError(f"{call.name} answered {type(output).__name__}")
    except Exception as failed:  # a tool bug is the run's failure, never the model's text
        _log.warning(
            "agent_tool.failed", tool=call.name, run_id=call.run_id, error=type(failed).__name__
        )
        if claim.id is not None:
            await _settle(agent, call, claim.id, None)
        return _refused(call.name, "tool_failed", started)
    rows, over = _row_count(the_tool, output)
    if over:
        if claim.id is not None:
            await _settle(agent, call, claim.id, None)
        return _refused(call.name, "row_limit", started)
    result = cast(dict[str, object], _scrub(output.model_dump(mode="json")))
    if claim.id is not None:
        await _settle(agent, call, claim.id, result)
    await _record(agent, the_tool, call, targets)
    return ToolOutcome(
        name=call.name,
        ok=True,
        result=result,
        records_read=rows,
        restricted=the_tool.data_class in ("restricted", "tri"),
        active_ms=_ms(started),
    )


def for_model(outcome: ToolOutcome, untrusted: Iterable[str] = ()) -> str:
    """The next turn's text for an outcome (AC-R5): trusted fields as JSON, each `untrusted` field
    in its own `<untrusted>` block, JSON-encoded with `<` escaped so client text can neither
    close the block nor pose as instructions (ADR-052). A refusal is its code alone."""
    if not outcome.ok or outcome.result is None:
        return json.dumps({"tool": outcome.name, "refused": outcome.code})
    hidden = set(untrusted) or set(_untrusted_of(outcome.name))
    trusted = {k: v for k, v in outcome.result.items() if k not in hidden}
    parts = [_encode({"tool": outcome.name, "result": trusted})]
    for name in sorted(k for k in outcome.result if k in hidden):
        parts.append(f'<untrusted name="{name}">\n{_encode(outcome.result[name])}\n</untrusted>')
    return "\n".join(parts)


def _untrusted_of(name: str) -> Sequence[str]:
    try:
        return tool(name).untrusted
    except ToolNotRegistered:
        return ()


def _encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str).replace("<", "\\u003c")
