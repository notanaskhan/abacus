"""`close.agent`'s flux and planner runs (C-01-T30; C-01 §3 F7, F2; SPEC-655 AC-21, AC-22, AC-49;
DEC-5413; red).

A person starts each; code drives the run inline on the capability's run row (A-09-T29's
`start_capability_run`, attributed "<person> via Agent"), so no new workflow type exists (C-01
§4.5: `FluxExplain` and `ClosePlanDraft` are runs of `close.agent`).

- **Flux** (`explain_line`): code gives the model the line's change and the month's register lines
  (this month's as money facts `c<n>`, last month's with the sign reversed as `p<n>`; payees and
  memos are untrusted text). The model groups facts into drivers; code sums them (`agent.settle`)
  and they must foot to the change. A run that does not foot is asked once more (`repair`), then
  ends **escalated**: it waits on a person and nothing is written. A footing run cites every line
  it used as a `ledger_line` citation that code verifies (an unverified one escalates the run),
  then writes one P-35 suggestion and the line's agent-authored explanation draft
  (`explained_draft`).
  A person adopts it by saving their own explanation; only then can a Manager or Partner accept.
- **Planner** (`draft_from_history`): code profiles the entity's last 14 months of closes and
  offers each balance-sheet account its closed procedure and source sets. The model picks per
  row or leaves a row out. Code writes a draft plan version drafted by the person with the
  run's id, and every row carries its suggestion (`drafted_suggestion_id`): the version cannot
  be published until a person adopts each row (AC-22, the 0881 trigger).

Synthetic firms only until the AI boundary is cleared for the firm (`ai_gateway.is_synthetic`);
`closes.agent` off answers 404. A shadow run writes nothing a person sees.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import CLOSES_AGENT
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.closes import agent as close_agent
from abacus.modules.closes import repository as repo
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden

MAX_LINES: Final = 60
HISTORY_MONTHS: Final = 14
FLUX_TARGET: Final = "analytic_line"
PLAN_TARGET: Final = "close_plan_version"


class AgentNotAvailable(DomainConflict):
    """The firm's AI boundary is not cleared for this capability yet."""

    code = "agent_not_available"


class RunNotRecorded(DomainConflict):
    code = "agent_run_not_recorded"


@dataclass(frozen=True)
class RunOutcome:
    run_id: UUID
    status: str  # succeeded, escalated, shadow
    reason: str | None = None


async def _available(ctx: AuthContext, action: str) -> None:
    from abacus.ai_gateway import is_synthetic

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")
    if not await flag_enabled(ctx.tenant, CLOSES_AGENT):
        raise NotFound(CLOSES_AGENT.name)
    if not await is_synthetic(ctx.tenant):
        raise AgentNotAvailable(facts={"capability": close_agent.CAPABILITY})


async def _start(ctx: AuthContext, engagement_id: UUID) -> tuple[AgentContext, bool]:
    from abacus.modules.agents.api import start_capability_run, starts_in_shadow

    agent = await start_capability_run(ctx, close_agent.CAPABILITY, engagement_id)
    if agent is None:
        raise RunNotRecorded(facts={"capability": close_agent.CAPABILITY})
    async with tenant_session(agent.tenant) as session:
        shadow = await starts_in_shadow(session, agent.tenant, close_agent.CAPABILITY)
    return agent, bool(shadow)


def plain_text(blocks: Mapping[str, object], facts: Mapping[str, close_agent.FactIn]) -> str:
    """The settled blocks as the sentence a person reads (fact tokens to their values)."""
    out: list[str] = []
    for part in cast("list[dict[str, object]]", blocks.get("parts") or []):
        words: list[str] = []
        for seg in cast("list[dict[str, object]]", part.get("segments") or []):
            if seg.get("kind") == "text":
                words.append(str(seg.get("text", "")))
            elif seg.get("kind") == "fact":
                fact = facts.get(str(seg.get("fact_id")))
                if fact is not None:
                    words.append(_shown(fact))
        out.append("".join(words).strip())
    return " ".join(p for p in out if p)[:2000]


def _shown(fact: close_agent.FactIn) -> str:
    if fact.kind == "money":
        return f"{Decimal(fact.value):,.2f}"
    if fact.kind == "percent":
        return f"{Decimal(fact.value):.1f}%"
    return fact.value


# --- flux ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LineFact:
    fact_id: str
    snapshot_id: UUID
    line_no: int
    raw: Decimal  # as the register prints it (what the citation claims)
    value: Decimal  # in the line's natural sign, reversed for a prior line
    note: str


def calibrate(raw_total: Decimal, activity: Decimal) -> int:
    """+1 when the register's lines add up to the month's activity as printed, else -1 (an
    income account's register prints credits negative)."""
    return 1 if abs(raw_total - activity) <= abs(raw_total + activity) else -1


def line_facts(
    prefix: str,
    lines: Sequence[tuple[UUID, int, Decimal, str]],
    activity: Decimal,
    *,
    reverse: bool,
) -> list[LineFact]:
    """The register lines as facts, largest first, at most `MAX_LINES`."""
    sign = calibrate(sum((x[2] for x in lines), Decimal(0)), activity) * (-1 if reverse else 1)
    ranked = sorted(lines, key=lambda x: (-abs(x[2]), x[1]))[:MAX_LINES]
    return [
        LineFact(f"{prefix}{n}", snap, no, raw, raw * sign, note)
        for n, (snap, no, raw, note) in enumerate(ranked, start=1)
    ]


async def _register(
    tenant: TenantContext, entity: UUID, account: str, period: str
) -> list[tuple[UUID, int, Decimal, str]]:
    from abacus.modules.ledger.api import PeriodNotAvailable, register_lines

    out: list[tuple[UUID, int, Decimal, str]] = []
    cursor: str | None = None
    try:
        for _ in range(20):
            rows, cursor = await register_lines(tenant, entity, account, period, cursor=cursor)
            for r in rows:
                snap, _, no = r.line_ref.rpartition(":")
                note = " — ".join(x for x in (r.payee, r.memo) if x)[:180]
                out.append((UUID(snap), int(no), r.amount, note))
            if cursor is None:
                break
    except PeriodNotAvailable:
        return []
    return out


_LINE: Final = text(
    "SELECT l.set_id, l.line_key, l.caption, l.prior, l.current, l.change, l.change_pct, l.test, "
    "l.status, s.close_id, s.basis FROM analytic_lines l JOIN analytic_sets s ON s.id = l.set_id "
    "WHERE md5(l.set_id::text || ':' || l.line_key)::uuid = :id"
)
_DRAFT: Final = text(
    "INSERT INTO analytic_explanations (tenant_id, close_id, line_key, version, text_sealed, "
    "drivers, citation_ids, author_kind, suggestion_id) VALUES (:t, :c, :k, :v, :sealed, "
    "CAST(:drivers AS jsonb), :cites, 'agent', :s) RETURNING id"
)
_TO_DRAFT: Final = text(
    "UPDATE analytic_lines SET status = 'explained_draft' WHERE set_id = :s AND line_key = :k "
    "AND status = 'unexplained'"
)


async def explain_line(ctx: AuthContext, line_id: UUID) -> RunOutcome:
    """`POST /analytic-lines/{id}/explain`: one flux run for one over-both-legs line."""
    import json

    from abacus.modules.closes import flux

    await _available(ctx, "flux.explain")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LINE, {"id": line_id})).mappings().first()
    if row is None:
        raise NotFound("analytic_line")
    close_id = cast(UUID, row["close_id"])
    engagement = await flux._authorise_close(ctx, close_id, "flux.explain")  # pyright: ignore[reportPrivateUsage] -- one module
    if row["test"] != "over_both":
        raise flux.NothingToExplain(facts={"line": str(row["line_key"])})
    if row["status"] == "accepted":
        raise flux.LineAccepted(facts={"line": str(row["line_key"])})
    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None or close.client_entity_id is None:
        raise NotFound("close")
    account = str(row["line_key"])
    before = flux.prior_period(close.period, cast(flux.Basis, row["basis"]))
    current = cast(Decimal, row["current"])
    prior = cast("Decimal | None", row["prior"]) or Decimal(0)
    now_lines = line_facts(
        "c", await _register(ctx.tenant, close.client_entity_id, account, close.period), current,
        reverse=False,
    )  # fmt: skip
    then_lines = line_facts(
        "p", await _register(ctx.tenant, close.client_entity_id, account, before), prior,
        reverse=True,
    )  # fmt: skip
    lines = {x.fact_id: x for x in now_lines + then_lines}
    facts = [
        close_agent.FactIn(id="change", kind="money", value=str(row["change"]), basis="code"),
        close_agent.FactIn(id="current", kind="money", value=str(current), basis="code"),
        close_agent.FactIn(id="prior", kind="money", value=str(prior), basis="code"),
        *(
            [close_agent.FactIn(id="change_pct", kind="percent", value=str(row["change_pct"]),
                                basis="code")]
            if row["change_pct"] is not None else []
        ),
        *(close_agent.FactIn(id=x.fact_id, kind="money", value=str(x.value), basis="register")
          for x in lines.values()),
    ]  # fmt: skip
    given = close_agent.CloseAgentInput(
        mode="flux",
        close_id=close_id,
        facts=facts,
        untrusted=[f"{x.fact_id}: {x.note}" for x in lines.values() if x.note][:250],
    )
    agent, shadow = await _start(ctx, engagement)
    settled, reason = await _flux_answer(agent, given)
    if settled is None:
        return await _end(agent, "escalated", reason)
    cited = await _cite(agent, line_id, close_id, engagement, account, settled, lines, shadow)
    if cited is None:
        return await _end(agent, "escalated", "citation_unverified")
    if shadow:
        return await _end(agent, "shadow", None, drivers=len(settled.drivers))
    by_fact = {fid: cid for fid, cid in cited}
    drivers = [
        {"label": d.label, "amount": str(d.amount),
         "citation_ids": [str(by_fact[f]) for f in d.fact_ids if f in by_fact]}
        for d in settled.drivers
    ]  # fmt: skip
    body = plain_text(cast("dict[str, object]", given_blocks(settled)), {f.id: f for f in facts})
    from abacus.modules.agents.api import create_suggestion

    suggestion = await create_suggestion(
        agent,
        engagement_id=engagement,
        target_type=FLUX_TARGET,
        target_id=line_id,
        field_key="explanation",
        proposed_value={"t": "json", "v": {"text": body, "drivers": drivers}},
        citation_ids=[cid for _, cid in cited][:50],
    )
    sealed = await seal(ctx.tenant_id, body.encode(), flux.FINGERPRINT)
    async with uow(agent.tenant) as tx:
        latest = await tx.session.scalar(
            text(
                "SELECT max(version) FROM analytic_explanations "
                "WHERE close_id = :c AND line_key = :k"
            ),
            {"c": close_id, "k": account},
        )
        made = await tx.session.scalar(
            _DRAFT,
            {"t": ctx.tenant_id, "c": close_id, "k": account, "v": int(latest or 0) + 1,
             "sealed": sealed, "drivers": json.dumps(drivers),
             "cites": [cid for _, cid in cited][:50], "s": suggestion},
        )  # fmt: skip
        await tx.session.execute(_TO_DRAFT, {"s": row["set_id"], "k": account})
        tx.record(
            "analytic_line.explanation_drafted",
            target=Target(flux.TARGET, cast(UUID, row["set_id"])),
            after=Ref(explanation=made, suggestion=suggestion, drivers=len(drivers)),
        )
    return await _end(agent, "succeeded", None, drivers=len(drivers))


def given_blocks(settled: close_agent.Settled) -> object:
    blocks = settled.blocks
    dump = getattr(blocks, "model_dump", None)
    return dump(mode="json") if callable(dump) else blocks


async def _flux_answer(
    agent: AgentContext, given: close_agent.CloseAgentInput
) -> tuple[close_agent.Settled | None, str | None]:
    """The model's drivers, asked again once when they do not foot; else the refusal's reason."""
    try:
        return await close_agent.answer(agent, given), None
    except close_agent.OutputRefused as refused:
        reason = str((refused.facts or {}).get("reason"))
    if reason != "drivers_do_not_foot":
        return None, reason
    try:
        return await close_agent.answer(
            agent, given.model_copy(update={"repair": "drivers_do_not_foot"})
        ), None
    except close_agent.OutputRefused as refused:
        return None, str((refused.facts or {}).get("reason"))


async def _cite(
    agent: AgentContext,
    line_id: UUID,
    close_id: UUID,
    engagement: UUID,
    account: str,
    settled: close_agent.Settled,
    lines: Mapping[str, LineFact],
    shadow: bool,
) -> list[tuple[str, UUID]] | None:
    """A `ledger_line` citation per register line a driver used, verified by code; None when any
    does not verify (the run escalates; the rows stay, unverified, as the trail shows)."""
    from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

    used = [lines[f] for d in settled.drivers for f in d.fact_ids if f in lines]
    if not used:
        return None
    claims = [
        CitationClaim(
            "ledger_line",
            {"ledger_snapshot_id": str(x.snapshot_id), "account_code": account,
             "register_line": x.line_no},
            value=str(x.raw),
        )
        for x in used
    ]  # fmt: skip
    anchor = CitationAnchor(FLUX_TARGET, line_id, None, None, engagement, work_item_id=close_id)
    async with uow(agent.tenant) as tx:
        recorded = await record_citations(
            tx, actor=agent, anchor=anchor, claims=claims, shadow=shadow
        )
    if len(recorded) != len(used) or not all(r.verified for r in recorded):
        return None
    return [(x.fact_id, r.id) for x, r in zip(used, recorded, strict=True)]


async def _end(agent: AgentContext, status: str, reason: str | None, **counts: int) -> RunOutcome:
    from abacus.modules.agents.api import end_capability_run

    output: dict[str, object] = dict(counts)
    if reason is not None:
        output["reason"] = reason[:60]
    await end_capability_run(
        agent, status="succeeded" if status == "shadow" else status, output=output
    )
    return RunOutcome(agent.agent_run_id, status, reason)


# --- planner -------------------------------------------------------------------------------------

# The closed sets code offers per QuickBooks account type (C-01 §3 F2; 0881's CHECKs). An account
# type outside the map is offered by its classification.
_BY_TYPE: Final[Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "Bank": (("reconciliation",), ("bank_feed", "client_upload", "quickbooks_online")),
    "Credit Card": (("reconciliation",), ("bank_feed", "client_upload")),
    "Accounts Receivable": (("aging", "clear_and_age"), ("quickbooks_online", "accrued_register")),
    "Other Current Asset": (
        ("amortization", "reconciliation", "rollforward", "clear_and_age", "third_party_sales"),
        ("accrued_register", "client_upload", "quickbooks_online", "files"),
    ),
    "Fixed Asset": (("depreciation", "rollforward"), ("accrued_register", "files")),
    "Other Asset": (
        ("amortization", "rollforward", "reconciliation"),
        ("accrued_register", "files", "client_upload"),
    ),
    "Accounts Payable": (("aging", "aging_cutoff"), ("quickbooks_online",)),
    "Other Current Liability": (
        ("accrual", "rollforward", "reconciliation", "tie_to_filings", "tie_to_return"),
        ("accrued_register", "client_upload", "files", "quickbooks_online"),
    ),
    "Long Term Liability": (("rollforward", "reconciliation"), ("client_upload", "files")),
    "Equity": (("rollforward",), ("quickbooks_online",)),
}
_BY_CLASS: Final[Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "asset": (("reconciliation", "rollforward"), ("client_upload", "files", "quickbooks_online")),
    "liability": (
        ("reconciliation", "rollforward", "accrual"),
        ("client_upload", "files", "quickbooks_online"),
    ),
    "equity": (("rollforward",), ("quickbooks_online",)),
}
# The method a drafted row starts with: the procedure's own name (a person edits it).
METHOD: Final[Mapping[str, str]] = {
    "reconciliation": "Reconcile to the statement",
    "aging": "Review the aging",
    "clear_and_age": "Clear and age open items",
    "third_party_sales": "Clear third-party sales",
    "rollforward": "Roll forward the balance",
    "amortization": "Amortize per schedule",
    "depreciation": "Depreciate per schedule",
    "aging_cutoff": "Review the aging and cutoff",
    "accrual": "Roll the accrual",
    "tie_to_return": "Tie to the return",
    "tie_to_filings": "Tie to the filings",
    "recategorize": "Recategorize per rules",
    "flux": "Review the flux",
}


def choices_for(account_type: str, classification: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return _BY_TYPE.get(account_type) or _BY_CLASS.get(classification) or ((), ())


@dataclass(frozen=True)
class PlanAccount:
    external_id: str
    name: str
    account_type: str
    procedures: tuple[str, ...]
    sources: tuple[str, ...]


_NEWEST_CLOSE: Final = text(
    "SELECT work_item_id, period FROM closes WHERE client_entity_id = :e "
    "ORDER BY period DESC LIMIT 1"
)
_HISTORY: Final = text(
    "SELECT count(DISTINCT c.period) FROM reconciliations r JOIN closes c "
    "ON c.work_item_id = r.close_id WHERE c.client_entity_id = :e AND c.period = ANY(:periods)"
)
_NEW_ROW: Final = text(
    "INSERT INTO close_plan_rows (tenant_id, version_id, position, account_external_id, "
    "account_name, account_class, procedure, method, source, review_level, frequency, "
    "drafted_suggestion_id) VALUES (:t, :v, :pos, :a, :name, :cls, :proc, :method, :src, "
    "'senior_signoff', 'monthly', :s)"
)


async def draft_from_history(ctx: AuthContext, client_id: UUID) -> tuple[RunOutcome, int | None]:
    """`POST /v1/clients/{id}/close-plan/draft-from-history`: the planner run and its draft."""
    from abacus.modules.closes import plans
    from abacus.modules.closes.registrations import closing_period
    from abacus.modules.ledger.api import PeriodNotAvailable, account_tree

    await _available(ctx, "close_plan.draft_from_history")
    ref = await plans._scope(ctx, client_id, "close_plan.draft_from_history")  # pyright: ignore[reportPrivateUsage] -- one module
    entity = ref.client_entity_id
    async with tenant_session(ctx.tenant) as session:
        newest = (await session.execute(_NEWEST_CLOSE, {"e": entity})).first()
    from abacus.kernel.clock import today

    period = str(newest.period) if newest is not None else closing_period(await today(ctx.tenant))
    try:
        tree = await account_tree(ctx.tenant, entity, period)
    except PeriodNotAvailable:
        raise NotFound("ledger_snapshot") from None
    accounts: list[PlanAccount] = []
    for a in tree.accounts:
        if a.classification not in ("asset", "liability", "equity"):
            continue
        procs, srcs = choices_for(a.account_type, a.classification)
        if procs:
            accounts.append(PlanAccount(a.external_id, a.name[:200], a.account_type, procs, srcs))
    periods: list[str] = []
    p = period
    for _ in range(HISTORY_MONTHS):
        periods.append(p)
        p = _prior(p)
    async with tenant_session(ctx.tenant) as session:
        months_seen = int(await session.scalar(_HISTORY, {"e": entity, "periods": periods}) or 0)
    keyed = {_key(a.external_id): a for a in accounts}
    given = close_agent.CloseAgentInput(
        mode="planner",
        close_id=newest.work_item_id if newest is not None else ref.id,
        facts=[
            close_agent.FactIn(id="months", kind="count", value=str(HISTORY_MONTHS), basis="code"),
            close_agent.FactIn(id="months_seen", kind="count", value=str(months_seen),
                               basis="code"),
            close_agent.FactIn(id="accounts", kind="count", value=str(len(keyed)), basis="code"),
        ],
        choices=[
            close_agent.PlanChoiceIn(row_key=k, procedures=list(a.procedures),
                                     sources=list(a.sources))
            for k, a in list(keyed.items())[:120]
        ],
        untrusted=[f"{k}: {a.name} ({a.account_type})" for k, a in keyed.items()][:250],
    )  # fmt: skip
    agent, shadow = await _start(ctx, ref.id)
    try:
        settled = await close_agent.answer(agent, given)
    except close_agent.OutputRefused as refused:
        return await _end(agent, "escalated", str((refused.facts or {}).get("reason"))), None
    if shadow:
        return await _end(agent, "shadow", None, rows=len(settled.rows)), None
    version = await _write_draft(ctx, agent, client_id, ref.id, settled, keyed)
    return await _end(agent, "succeeded", None, rows=len(settled.rows)), version


def _key(external_id: str) -> str:
    from abacus.modules.closes.flux import line_key

    return line_key(external_id)[:64]


def _prior(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{year - 1:04d}-12" if month == 1 else f"{year:04d}-{month - 1:02d}"


async def _write_draft(
    ctx: AuthContext,
    agent: AgentContext,
    client_id: UUID,
    engagement: UUID,
    settled: close_agent.Settled,
    keyed: Mapping[str, PlanAccount],
) -> int:
    """A new draft version drafted by the person with the run's id, its rows each a suggestion."""
    from abacus.modules.agents.api import create_suggestion
    from abacus.modules.closes import plans

    version_id, number = await plans.new_agent_draft(ctx, client_id, agent.agent_run_id)
    for pos, row in enumerate(settled.rows):
        account = keyed[row.row_key]
        suggestion = await create_suggestion(
            agent,
            engagement_id=engagement,
            target_type=PLAN_TARGET,
            target_id=version_id,
            field_key=f"row:{row.row_key}"[:120],
            proposed_value={
                "t": "json",
                "v": {"procedure": row.procedure, "source": row.source},
            },
        )
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                _NEW_ROW,
                {"t": ctx.tenant_id, "v": version_id, "pos": pos, "a": account.external_id,
                 "name": account.name, "cls": account.account_type[:64] or "Account",
                 "proc": row.procedure, "method": METHOD[row.procedure], "src": row.source,
                 "s": suggestion},
            )  # fmt: skip
            tx.record(
                "close_plan_row.drafted",
                target=Target("close_plan_version", version_id),
                after=Ref(suggestion=suggestion, position=pos),
            )
    return number


# --- suggestion targets --------------------------------------------------------------------------


async def analytic_line_engagement(tenant: TenantContext, line_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text(
                "SELECT c.engagement_id FROM analytic_lines l JOIN analytic_sets s "
                "ON s.id = l.set_id JOIN closes c ON c.work_item_id = s.close_id "
                "WHERE md5(l.set_id::text || ':' || l.line_key)::uuid = :id"
            ),
            {"id": line_id},
        )


async def plan_version_engagement(tenant: TenantContext, version_id: UUID) -> UUID | None:
    from abacus.modules.closes.gate_sources import (
        _monthly_close_of,  # pyright: ignore[reportPrivateUsage] -- one module
    )

    async with tenant_session(tenant) as session:
        entity = await session.scalar(
            text(
                "SELECT p.client_entity_id FROM close_plan_versions v JOIN close_plans p "
                "ON p.id = v.plan_id WHERE v.id = :v"
            ),
            {"v": version_id},
        )
    return None if entity is None else await _monthly_close_of(tenant, cast(UUID, entity))


def register() -> None:
    from abacus.modules.agents.api import register_suggestion_target

    register_suggestion_target(FLUX_TARGET, engagement_of=analytic_line_engagement)
    register_suggestion_target(PLAN_TARGET, engagement_of=plan_version_engagement)


__all__ = [
    "AgentNotAvailable",
    "RunOutcome",
    "calibrate",
    "choices_for",
    "draft_from_history",
    "explain_line",
    "line_facts",
    "plain_text",
    "register",
]
