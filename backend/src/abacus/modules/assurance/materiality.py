"""A-04-T12: the materiality service AUD-07 reads (A-04 §3.3 AC3.1-AC3.9; SPEC-620; DEC-1950).

The record is 0613's insert-only `materiality_versions` on the audit work item. Every figure is
the engine's (`compute/materiality.py`, ADR-050) over C9's trial balance and the firm's K-02
`materiality_ranges` policy; the browser does no arithmetic and nothing here asks a model.

- **Propose** (a manager or senior): the policy's benchmark is read from the chosen trial balance,
  the options are the engine's (the bottom of the firm range and its midpoint, plus a rate the
  proposer typed inside the range), and the `planning_materiality` card is raised through
  `review.api.raise_decision_card`, reserved to the engagement partner with a fresh second
  factor and a rationale. v1 "Proposed" names that card.
- **Decide** (the engagement partner, through C3's decide): the kind's applier writes the next
  version "Decided" from the chosen option's figures in the decider's own unit of work, with
  `materiality.decided`; the earlier version reads Superseded (derived).
- **Reassess** (a manager or senior, once decided): the Final layer at the decided rate and its
  difference from the decided overall, by code; the `materiality_reassessment` card offers
  **No change** (the thresholds stand) or **Revise** (the final-basis thresholds, with the
  impact list the registered dependents compute and `materiality_revised` to their preparers).

Client principals never reach any of it (the contract's gate, INV-4).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import FetchedValue, func, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.clock import now, today
from abacus.kernel.db import Base, TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.numeric import quantize_half_up
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.assurance.compute import materiality as engine
from abacus.modules.assurance.events import (
    MaterialityDecided,
    MaterialityReassessed,
    MaterialityRevised,
)
from abacus.modules.engagements.api import (
    assurance_item,
    assurance_item_id,
    get_ref,
    prior_engagement_of,
)
from abacus.modules.identity.api import AuthContext, allowed_actions, names_of
from abacus.modules.ledger.api import mapped_trial_balance, trial_balance_view
from abacus.modules.methodology.api import (
    MaterialityRangesPayload,
    PolicyRef,
    current_version_of_kind,
    policy_payload,
)
from abacus.modules.review.api import (
    AppliedDecision,
    CardContext,
    CardOption,
    CardSubject,
    ComputedCard,
    DecisionKind,
    awaiting_cards,
    raise_decision_card,
    register_decision_kind,
)

PROPOSE_KIND: Final = "planning_materiality"
REASSESS_KIND: Final = "materiality_reassessment"
KINDS: Final = (PROPOSE_KIND, REASSESS_KIND)
_DECIDED: Final = ("decided", "revised")  # a version whose thresholds are in force
_STOP: Final = frozenset({"available", "for", "to", "of", "and", "from", "in", "on"})
_WORD: Final = re.compile(r"[a-z0-9]+")


class MaterialityVersion(Base):
    __tablename__ = "materiality_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    version_no: Mapped[int]
    status: Mapped[str]
    basis: Mapped[str]
    tb_snapshot_id: Mapped[UUID | None]
    tb_layer: Mapped[str | None]
    benchmarks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # Any: JSON
    benchmark_key: Mapped[str]
    rate_pct: Mapped[Decimal]
    overall: Mapped[Decimal]
    pm_pct: Mapped[Decimal]
    pm: Mapped[Decimal]
    ct_pct: Mapped[Decimal]
    ct: Mapped[Decimal]
    specific: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)  # Any: JSON
    qualitative_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # Any: JSON
    prior_year_overall: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    policy_version_id: Mapped[UUID | None]
    decision_card_id: Mapped[UUID | None]
    decision_id: Mapped[UUID | None]
    reassessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    impact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    engine_name: Mapped[str]
    engine_version: Mapped[str]
    inputs_hash: Mapped[str]
    computed_at: Mapped[datetime]
    created_by_kind: Mapped[str]
    created_by_user_id: Mapped[UUID]
    on_behalf_of_user_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


# --- errors (409/422 codes in docs/architecture/error-codes.yaml) ------------------------------


class OutsidePolicy(DomainConflict):
    """A rate, PM or CT outside the firm's K-02 policy (AC3.3); `facts.field` names which."""

    code = "outside_policy"


class PolicyMissing(DomainConflict):
    """The firm has no materiality policy in effect for this kind of audit."""

    code = "materiality_policy_missing"


class BenchmarkNotFound(DomainInvalid):
    """The trial balance holds no line for the policy's benchmark."""

    code = "benchmark_not_found"


class ProposalPending(DomainConflict):
    """A materiality card already waits on the engagement partner."""

    code = "proposal_pending"


class NothingDecided(DomainConflict):
    """A reassessment needs a decided materiality."""

    code = "nothing_decided"


class MaterialityRecordMoved(DomainConflict):
    """The card's version is no longer the record's newest (a later version was written)."""

    code = "materiality_record_moved"


# --- the firm policy and the trial balance ------------------------------------------------------


@dataclass(frozen=True)
class FirmPolicy:
    ref: PolicyRef
    engagement_kind: str
    benchmark_key: str
    benchmark_label: str
    policy: engine.Policy


def benchmark_key(label: str) -> str:
    """The benchmark's key from its label, to the first connecting word: "Net assets available
    for benefits" -> "net_assets", "Pre-tax income" -> "pre_tax_income"."""
    words: list[str] = []
    for word in _WORD.findall(label.casefold()):
        if word in _STOP and words:
            break
        words.append(word)
    key = "_".join(words)[:64]
    if not key or not key[0].isalpha():
        raise BenchmarkNotFound(facts={"field": "benchmark_key"})
    return key


def _kind_matches(engagement_kind: str, segment: str, plan: str | None) -> bool:
    """The policy row for the audit's segment (the index's: EBP, FS, review); a defined-benefit
    plan reads its own row when the firm keeps one."""
    text = engagement_kind.casefold()
    if segment == "ebp":
        benefit = "defined benefit" in text
        return text.startswith("ebp") and benefit == (plan == "db")
    if segment == "fs":
        return text.startswith(("for-profit", "fs audit", "financial statement"))
    return False


async def firm_policy(tenant: TenantContext, work_item_id: UUID, as_of: date) -> FirmPolicy:
    """The firm's materiality range for this audit, from the K-02 version in effect."""
    item = await assurance_item(tenant, work_item_id)
    found = await current_version_of_kind(tenant.tenant_id, "materiality_ranges", as_of)
    if found is None:
        raise PolicyMissing
    payload = MaterialityRangesPayload.model_validate(
        await policy_payload(tenant.tenant_id, found, "materiality_ranges")
    )
    if item.ebp_plan_kind is not None or item.assurance_type.startswith("ebp"):
        segment = "ebp"
    else:
        segment = "fs" if item.assurance_type == "fs_audit" else "review"
    row = next(
        (r for r in payload.rows if _kind_matches(r.engagement_kind, segment, item.ebp_plan_kind)),
        None,
    )
    if row is None:
        raise PolicyMissing(facts={"field": "engagement_kind"})
    pm = payload.performance_materiality
    return FirmPolicy(
        found,
        row.engagement_kind,
        benchmark_key(row.benchmark),
        row.benchmark,
        engine.Policy(
            low_pct=row.low_pct,
            high_pct=row.high_pct,
            pm_low_pct=pm.low_pct,
            pm_high_pct=pm.high_pct,
            ct_pct=payload.clearly_trivial_pct,
        ),
    )


@dataclass(frozen=True)
class BenchmarkRead:
    amount: Decimal
    period_end: date
    tb_id: UUID
    layer: str


async def read_benchmark(
    tenant: TenantContext, engagement_id: UUID, tb_id: UUID, label: str, layer: str
) -> BenchmarkRead:
    """The benchmark's amount on a layer (C9): the lines named as the policy names it, else the
    mapped FS line of that name (Unadjusted); the absolute net, by code."""
    view = await trial_balance_view(tenant, engagement_id, tb_id, layer=layer)
    wanted = " ".join(label.casefold().split())
    lines = [ln for ln in view.lines if " ".join(ln.account_name.casefold().split()) == wanted]
    if lines:
        total = sum(
            (
                (ln.final if ln.final is not None else ln.eoy) if layer == "final" else ln.eoy
                for ln in lines
            ),
            Decimal(0),
        )
        return BenchmarkRead(abs(total), view.summary.period_end, tb_id, layer)
    if layer == "unadjusted":
        mapped = await mapped_trial_balance(tenant, engagement_id, tb_id)
        rows = [
            m
            for m in (mapped.lines if mapped is not None else [])
            if " ".join(m.fs_line_label.casefold().split()) == wanted
        ]
        if rows:
            total = sum((m.net for m in rows), Decimal(0))
            return BenchmarkRead(abs(total), view.summary.period_end, tb_id, layer)
    raise BenchmarkNotFound(facts={"field": "benchmark_key"})


# --- reads ----------------------------------------------------------------------------------


async def _work_item(ctx: AuthContext | TenantContext, engagement_id: UUID) -> UUID:
    tenant = ctx if isinstance(ctx, TenantContext) else ctx.tenant
    found = await assurance_item_id(tenant, engagement_id)
    if found is None:
        raise NotFound("materiality")
    return found


async def versions_of(tenant: TenantContext, work_item_id: UUID) -> list[MaterialityVersion]:
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(MaterialityVersion)
                    .where(MaterialityVersion.work_item_id == work_item_id)
                    .order_by(MaterialityVersion.version_no)
                )
            ).scalars()
        )


def in_force(versions: Sequence[MaterialityVersion]) -> MaterialityVersion | None:
    """The version whose thresholds stand: the newest decided or revised one; a No-change
    reassessment keeps the decided thresholds it copied."""
    for v in reversed(versions):
        if v.status in (*_DECIDED, "reassessed"):
            return v
    return None


def current_of(versions: Sequence[MaterialityVersion]) -> MaterialityVersion | None:
    """The record's current version: the newest; every earlier one reads Superseded."""
    return versions[-1] if versions else None


@dataclass(frozen=True)
class PriorYearFact:
    year: str
    amount: Decimal
    overall_used: Decimal
    rate_used_pct: Decimal


async def prior_years(
    tenant: TenantContext, engagement_id: UUID, key: str, limit: int = 2
) -> list[PriorYearFact]:
    """The benchmark and the final overall of the engagements this one rolled forward from, as
    their own decided versions recorded them (AC3.2); nothing the browser computes."""
    out: list[PriorYearFact] = []
    current = engagement_id
    for _ in range(limit):
        prior = await prior_engagement_of(tenant, current)
        if prior is None:
            break
        current = prior
        item = await assurance_item_id(tenant, prior)
        if item is None:
            continue
        decided = in_force(await versions_of(tenant, item))
        if decided is None or decided.benchmark_key != key:
            continue
        row = next((b for b in decided.benchmarks if b.get("key") == key), None)
        if row is None or not row.get("period_end"):
            continue
        out.append(
            PriorYearFact(
                f"PY{str(row['period_end'])[:4]}",
                Decimal(str(row["amount"])),
                decided.overall,
                decided.rate_pct,
            )
        )
    return out


@dataclass(frozen=True)
class MaterialityRecord:
    work_item_id: UUID
    versions: list[MaterialityVersion]
    names: dict[UUID, str]
    benchmarks: tuple[engine.Benchmark, ...]
    priors: list[PriorYearFact]
    period_end: date | None
    policy_version_id: UUID | None
    pending_card_id: UUID | None
    pending_reserved_user_id: UUID | None
    actions: list[str]
    caption: list[str]


def _stored_benchmarks(
    version: MaterialityVersion, priors: Sequence[PriorYearFact]
) -> tuple[engine.Benchmark, ...]:
    """The version's benchmark rows, re-run through the engine at its rate with the prior years:
    the same inputs give the same figures and hash (ADR-050)."""
    items = tuple(
        engine.BenchmarkInput(
            key=str(b["key"]),
            label=str(b["label"]),
            amount=Decimal(str(b["amount"])),
            low_pct=Decimal(str(b["range_low_pct"])),
            high_pct=Decimal(str(b["range_high_pct"])),
            use=cast(
                Literal["overall", "specific", "considered_for_specific", "not_used"], b["use"]
            ),
            prior_years=tuple(
                engine.PriorYear(p.year, p.amount, p.overall_used)
                for p in priors
                if str(b["key"]) == version.benchmark_key
            ),
        )
        for b in version.benchmarks
    )
    return engine.benchmarks(items, rate_pct=version.rate_pct)


def _caption(rows: Sequence[engine.Benchmark], priors: Sequence[PriorYearFact]) -> list[str]:
    """The sentences under the table, from code facts only (AC3.2)."""
    lines: list[str] = []
    overall = next((b for b in rows if b.use == "overall"), None)
    if overall is not None and priors:
        used = " · ".join(
            f"{p.year} {_pct(p.rate_used_pct)}% = {_whole(p.overall_used)}" for p in priors
        )
        lines.append(f"Overall materiality used: {used} (final, audited)")
        if overall.growth_pct is not None:
            direction = "up" if overall.growth_pct >= 0 else "down"
            lines.append(
                f"{overall.label} {direction} {abs(overall.growth_pct)}% on {priors[0].year}; "
                "today's thresholds do not use prior years."
            )
    return lines


def _pct(value: Decimal) -> str:
    return format(value.normalize(), "f") if value != value.to_integral() else f"{value:.1f}"


def _whole(value: Decimal) -> str:
    return f"{value:,.0f}"


async def record(ctx: AuthContext, engagement_id: UUID) -> MaterialityRecord:
    """`GET …/materiality/current` (the route authorised `materiality.read` and the flag)."""
    work_item = await _work_item(ctx, engagement_id)
    versions = await versions_of(ctx.tenant, work_item)
    newest = current_of(versions)
    priors = (
        await prior_years(ctx.tenant, engagement_id, newest.benchmark_key)
        if newest is not None
        else []
    )
    rows = _stored_benchmarks(newest, priors) if newest is not None else ()
    names = await names_of(sorted({v.created_by_user_id for v in versions}))
    waiting = await awaiting_cards(ctx.tenant, work_item, KINDS)
    pending = waiting[-1] if waiting else None
    ref = await get_ref(ctx, engagement_id)
    can = set(
        await allowed_actions(
            ctx, ref.resource(), ("materiality.propose", "materiality.reassess", "decision.notify")
        )
    )
    actions: list[str] = []
    if "materiality.propose" in can and pending is None:
        actions.append("materiality.propose")
    if "materiality.reassess" in can and pending is None and in_force(versions) is not None:
        actions.append("materiality.reassess")
    if pending is not None and pending.reserved_user_id == ctx.user_id:
        actions.append("decision.decide")  # C3 checks the reserved role and the second factor
    if (
        pending is not None
        and "decision.notify" in can
        and pending.reserved_user_id != ctx.user_id
    ):
        actions.append("decision.notify")
    period = None
    if newest is not None and newest.benchmarks and newest.benchmarks[0].get("period_end"):
        period = date.fromisoformat(str(newest.benchmarks[0]["period_end"]))
    return MaterialityRecord(
        work_item_id=work_item,
        versions=versions,
        names=names,
        benchmarks=rows,
        priors=priors,
        period_end=period,
        policy_version_id=newest.policy_version_id if newest is not None else None,
        pending_card_id=pending.card_id if pending is not None else None,
        pending_reserved_user_id=pending.reserved_user_id if pending is not None else None,
        actions=actions,
        caption=_caption(rows, priors),
    )


def _outside(exc: engine.OutsidePolicy) -> OutsidePolicy:
    return OutsidePolicy(facts={"field": exc.field})


async def preview(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    basis: Literal["unadjusted", "final"],
    key: str,
    rate_pct: Decimal,
    pm_pct: Decimal,
    ct_pct: Decimal,
) -> engine.Thresholds:
    """`POST …/materiality/preview`: the slider's thresholds by code; writes nothing (AC3.3).
    The benchmark amount is the record's own for that basis."""
    work_item = await _work_item(ctx, engagement_id)
    versions = await versions_of(ctx.tenant, work_item)
    newest = current_of(versions)
    if newest is None:
        raise NothingDecided(facts={"field": "benchmark_key"})
    policy = await firm_policy(ctx.tenant, work_item, await today(ctx.tenant))
    row = next((b for b in newest.benchmarks if b.get("key") == key), None)
    if row is None:
        raise BenchmarkNotFound(facts={"field": "benchmark_key"})
    try:
        return engine.preview(
            basis=basis,
            benchmark_key=key,
            benchmark_amount=Decimal(str(row["amount"])),
            rate_pct=rate_pct,
            pm_pct=pm_pct,
            ct_pct=ct_pct,
            policy=policy.policy,
        )
    except engine.OutsidePolicy as exc:
        raise _outside(exc) from None


# --- the cards -----------------------------------------------------------------------------------

# The card the service computed for the raise in flight: `raise_decision_card` asks the kind's
# provider for the options, and the provider answers with exactly what the service computed (one
# computation, no second read of the ledger between them).
_IN_FLIGHT: ContextVar[ComputedCard | None] = ContextVar("materiality_card", default=None)


@contextmanager
def _computed(card: ComputedCard) -> Iterator[None]:
    token = _IN_FLIGHT.set(card)
    try:
        yield
    finally:
        _IN_FLIGHT.reset(token)


async def _provided(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The kinds' provider: only the service raises these cards, with its computed options; any
    other caller is refused (fail closed)."""
    del tenant, subject
    found = _IN_FLIGHT.get()
    if found is None:
        raise DomainInvalid(facts={"field": "options"})
    return found


def _figures(t: engine.Thresholds) -> dict[str, str]:
    return {
        "basis": t.basis,
        "benchmark_key": t.benchmark_key,
        "benchmark_amount": format(t.benchmark_amount, "f"),
        "rate_pct": format(t.rate_pct, "f"),
        "overall": format(t.overall, "f"),
        "pm_pct": format(t.pm_pct, "f"),
        "pm": format(t.pm, "f"),
        "ct_pct": format(t.ct_pct, "f"),
        "ct": format(t.ct, "f"),
        "policy_low_pct": format(t.policy_low_pct, "f"),
        "policy_high_pct": format(t.policy_high_pct, "f"),
        "inputs_hash": t.stamp.inputs_hash,
    }


def _option_label(t: engine.Thresholds) -> str:
    """ "1.5% of net assets — $252,200" (the AUD-07 card's option copy)."""
    noun = t.benchmark_key.replace("_", " ")
    return f"{_pct(t.rate_pct)}% of {noun} — ${_whole(t.overall)}"


def _benchmark_json(
    key: str, label: str, read: BenchmarkRead, policy: engine.Policy
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "amount": format(quantize_half_up(read.amount, 2), "f"),
        "range_low_pct": format(policy.low_pct, "f"),
        "range_high_pct": format(policy.high_pct, "f"),
        "use": "overall",
        "period_end": read.period_end.isoformat(),
        "tb_id": str(read.tb_id),
        "layer": read.layer,
    }


@dataclass(frozen=True)
class Proposal:
    version: MaterialityVersion
    card_id: UUID
    options: tuple[engine.Option, ...]


async def propose(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    tb_id: UUID,
    key: str,
    rate_pct: Decimal | None,
) -> Proposal:
    """`POST …/materiality/proposals` (the route authorised `materiality.propose`): compute the
    options on the Unadjusted layer, raise the card, write v-next "Proposed" naming it."""
    work_item = await _work_item(ctx, engagement_id)
    if await awaiting_cards(ctx.tenant, work_item, KINDS):
        raise ProposalPending
    policy = await firm_policy(ctx.tenant, work_item, await today(ctx.tenant))
    if key != policy.benchmark_key:
        raise BenchmarkNotFound(facts={"field": "benchmark_key"})
    read = await read_benchmark(
        ctx.tenant, engagement_id, tb_id, policy.benchmark_label, "unadjusted"
    )
    pm_pct = policy.policy.pm_high_pct
    ct_pct = policy.policy.ct_pct
    try:
        options = engine.options(
            basis="unadjusted",
            benchmark_key=key,
            benchmark_amount=read.amount,
            pm_pct=pm_pct,
            ct_pct=ct_pct,
            policy=policy.policy,
        )
        typed = None
        if rate_pct is not None:
            typed = engine.thresholds(
                basis="unadjusted",
                benchmark_key=key,
                benchmark_amount=read.amount,
                rate_pct=rate_pct,
                pm_pct=pm_pct,
                ct_pct=ct_pct,
                policy=policy.policy,
            )
    except engine.OutsidePolicy as exc:
        raise _outside(exc) from None
    computed = [o for o in options if o.thresholds is not None]
    if typed is not None and all(o.key != engine.option_key(typed.rate_pct) for o in computed):
        computed.append(engine.Option(engine.option_key(typed.rate_pct), typed))
    first = cast(engine.Thresholds, computed[0].thresholds)
    card = ComputedCard(
        options=tuple(
            CardOption(
                o.key,
                _option_label(cast(engine.Thresholds, o.thresholds)),
                _figures(cast(engine.Thresholds, o.thresholds)),
            )
            for o in computed
        ),
        context=(
            CardContext("benchmark", "Benchmark", policy.benchmark_label),
            CardContext("amount", "Amount", _whole(read.amount)),
            CardContext(
                "firm_range",
                "Firm range",
                f"{_pct(policy.policy.low_pct)}%\N{EN DASH}{_pct(policy.policy.high_pct)}%",
            ),
            CardContext("period_end", "Period end", read.period_end.isoformat()),
        ),
    )
    with _computed(card):
        card_id = await raise_decision_card(
            ctx,
            engagement_id=engagement_id,
            kind=PROPOSE_KIND,
            question_key=f"materiality.{key}",
            work_item_id=work_item,
        )
    benchmarks = [_benchmark_json(key, policy.benchmark_label, read, policy.policy)]
    async with uow(ctx.tenant) as tx:
        version = await _insert(
            tx,
            ctx,
            work_item,
            engagement_id,
            status="proposed",
            thresholds=first,
            basis="unadjusted",
            tb_id=tb_id,
            benchmarks=benchmarks,
            policy_version_id=policy.ref.version_id,
            card_id=card_id,
            decision_id=None,
        )
        tx.record(
            "materiality_version.proposed",
            target=Target("materiality_version", version),
            after=Ref(card=card_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item),
        )
    found = await _version(ctx.tenant, version)
    return Proposal(found, card_id, tuple(computed))


async def _version(tenant: TenantContext, version_id: UUID) -> MaterialityVersion:
    async with tenant_session(tenant) as session:
        found = await session.get(MaterialityVersion, version_id)
    if found is None:
        raise NotFound("materiality")
    return found


async def _insert(
    tx: UnitOfWork,
    ctx: AuthContext,
    work_item_id: UUID,
    engagement_id: UUID,
    *,
    status: str,
    thresholds: engine.Thresholds,
    basis: str,
    tb_id: UUID | None,
    benchmarks: list[dict[str, object]],
    policy_version_id: UUID | None,
    card_id: UUID | None,
    decision_id: UUID | None,
    reassessment: dict[str, object] | None = None,
    impact: dict[str, object] | None = None,
) -> UUID:
    """The next version under the engagement lock the caller holds (versions are insert-only)."""
    latest = await tx.session.scalar(
        select(func.max(MaterialityVersion.version_no)).where(
            MaterialityVersion.work_item_id == work_item_id
        )
    )
    return (
        await tx.session.execute(
            insert(MaterialityVersion)
            .values(
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                version_no=(latest or 0) + 1,
                status=status,
                basis=basis,
                tb_snapshot_id=tb_id,
                tb_layer="final" if basis == "final" else "unadjusted",
                benchmarks=benchmarks,
                benchmark_key=thresholds.benchmark_key,
                rate_pct=thresholds.rate_pct,
                overall=thresholds.overall,
                pm_pct=thresholds.pm_pct,
                pm=thresholds.pm,
                ct_pct=thresholds.ct_pct,
                ct=thresholds.ct,
                qualitative_factors=[],
                policy_version_id=policy_version_id,
                decision_card_id=card_id,
                decision_id=decision_id,
                reassessment=reassessment,
                impact=impact,
                engine_name=thresholds.stamp.engine_name,
                engine_version=thresholds.stamp.engine_version,
                inputs_hash=thresholds.stamp.inputs_hash,
                computed_at=await now(ctx.tenant),
                created_by_kind=ctx.tenant.actor_kind,
                created_by_user_id=ctx.user_id,
            )
            .returning(MaterialityVersion.id)
        )
    ).scalar_one()


def thresholds_of(version: MaterialityVersion) -> engine.Thresholds:
    """A stored version as the engine's figures (its own stamp)."""
    row = next((b for b in version.benchmarks if b.get("key") == version.benchmark_key), {})
    amount = Decimal(str(row.get("amount", "0")))
    low = Decimal(str(row.get("range_low_pct", version.rate_pct)))
    high = Decimal(str(row.get("range_high_pct", version.rate_pct)))
    return engine.Thresholds(
        basis=cast(Literal["unadjusted", "final"], version.basis),
        benchmark_key=version.benchmark_key,
        benchmark_amount=amount,
        rate_pct=version.rate_pct,
        overall=version.overall,
        pm_pct=version.pm_pct,
        pm=version.pm,
        ct_pct=version.ct_pct,
        ct=version.ct,
        policy_low_pct=low,
        policy_high_pct=high,
        stamp=engine.Stamp(version.engine_name, version.engine_version, version.inputs_hash),
    )


def _from_figures(figures: dict[str, str]) -> engine.Thresholds:
    return engine.Thresholds(
        basis=cast(Literal["unadjusted", "final"], figures["basis"]),
        benchmark_key=figures["benchmark_key"],
        benchmark_amount=Decimal(figures["benchmark_amount"]),
        rate_pct=Decimal(figures["rate_pct"]),
        overall=Decimal(figures["overall"]),
        pm_pct=Decimal(figures["pm_pct"]),
        pm=Decimal(figures["pm"]),
        ct_pct=Decimal(figures["ct_pct"]),
        ct=Decimal(figures["ct"]),
        policy_low_pct=Decimal(figures["policy_low_pct"]),
        policy_high_pct=Decimal(figures["policy_high_pct"]),
        stamp=engine.Stamp(engine.ENGINE_NAME, engine.ENGINE_VERSION, figures["inputs_hash"]),
    )


async def _locked_versions(tx: UnitOfWork, work_item_id: UUID) -> list[MaterialityVersion]:
    return list(
        (
            await tx.session.execute(
                select(MaterialityVersion)
                .where(MaterialityVersion.work_item_id == work_item_id)
                .order_by(MaterialityVersion.version_no)
            )
        ).scalars()
    )


async def _apply_decision(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    """The `planning_materiality` applier: the chosen option's figures as the next version,
    "Decided", in the decision's unit of work (AC3.4, AC3.8)."""
    if decided.work_item_id is None:
        raise DomainInvalid(facts={"field": "work_item_id"})
    versions = await _locked_versions(tx, decided.work_item_id)
    proposed = next((v for v in versions if v.decision_card_id == decided.card_id), None)
    if proposed is None or versions[-1].id != proposed.id:
        raise MaterialityRecordMoved
    chosen = _from_figures(dict(decided.figures))
    version = await _insert(
        tx,
        ctx,
        decided.work_item_id,
        decided.engagement_id,
        status="decided",
        thresholds=chosen,
        basis="unadjusted",
        tb_id=proposed.tb_snapshot_id,
        benchmarks=list(proposed.benchmarks),
        policy_version_id=proposed.policy_version_id,
        card_id=decided.card_id,
        decision_id=decided.decision_id,
    )
    scope = Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id)
    tx.record(
        "materiality_version.decided",
        target=Target("materiality_version", version),
        after=Ref(decision=decided.decision_id),
        scope=scope,
    )
    tx.emit(
        MaterialityDecided(
            version_id=version,
            engagement_id=decided.engagement_id,
            work_item_id=decided.work_item_id,
            decision_id=decided.decision_id,
        )
    )


# --- reassessment ------------------------------------------------------------------------------

# The workpapers a revision touches (AC3.7): owners register a provider that answers, by code,
# which of their records cite materiality fields or depend on the materiality step.


@dataclass(frozen=True)
class Impacted:
    workpaper_code: str
    title: str
    reason: Literal["cites_materiality", "depends_on_step"]
    preparer_user_id: UUID | None


ImpactProvider = Callable[[TenantContext, UUID], Awaitable[list[Impacted]]]
_IMPACT: dict[str, ImpactProvider] = {}


def register_materiality_dependents(owner: str, provider: ImpactProvider) -> None:
    """`assurance.api.register_materiality_dependents`: one provider per owning module."""
    known = _IMPACT.get(owner)
    if known is not None and known is not provider:
        raise ValueError(f"materiality dependents {owner!r} already registered")
    _IMPACT[owner] = provider


async def impact_of(tenant: TenantContext, work_item_id: UUID) -> list[Impacted]:
    found: list[Impacted] = []
    for owner in sorted(_IMPACT):
        found.extend(await _IMPACT[owner](tenant, work_item_id))
    return sorted(found, key=lambda i: (i.workpaper_code, i.reason))


@dataclass(frozen=True)
class ReassessmentRaised:
    card_id: UUID
    reassessment: engine.Reassessment


async def reassess(ctx: AuthContext, engagement_id: UUID, *, tb_id: UUID) -> ReassessmentRaised:
    """`POST …/materiality/reassessments` (the route authorised `materiality.reassess`): the
    Final layer at the decided rate (AC3.6), and the card with No change or Revise."""
    work_item = await _work_item(ctx, engagement_id)
    if await awaiting_cards(ctx.tenant, work_item, KINDS):
        raise ProposalPending
    versions = await versions_of(ctx.tenant, work_item)
    standing = in_force(versions)
    if standing is None:
        raise NothingDecided
    policy = await firm_policy(ctx.tenant, work_item, await today(ctx.tenant))
    decided = thresholds_of(standing)
    label = next(
        (str(b["label"]) for b in standing.benchmarks if b.get("key") == standing.benchmark_key),
        policy.benchmark_label,
    )
    read = await read_benchmark(ctx.tenant, engagement_id, tb_id, label, "final")
    outcome = engine.reassess(decided, final_amount=read.amount, increment=policy.policy.increment)
    try:
        revised = engine.thresholds(
            basis="final",
            benchmark_key=standing.benchmark_key,
            benchmark_amount=read.amount,
            rate_pct=standing.rate_pct,
            pm_pct=standing.pm_pct,
            ct_pct=standing.ct_pct,
            policy=policy.policy,
        )
    except engine.OutsidePolicy as exc:
        raise _outside(exc) from None
    facts = {
        "final_amount": format(outcome.final_amount, "f"),
        "at_rate": format(outcome.at_rate, "f"),
        "difference": format(outcome.difference, "f"),
        "difference_pct": format(outcome.difference_pct, "f"),
        "final_tb_id": str(tb_id),
        "final_period_end": read.period_end.isoformat(),
        "inputs_hash": outcome.stamp.inputs_hash,
        "standing_version": str(standing.version_no),
    }
    card = ComputedCard(
        options=(
            CardOption(
                "no_change",
                f"No change — ${_whole(decided.overall)} stands",
                facts,
            ),
            CardOption(
                "revise",
                f"Revise to {_pct(revised.rate_pct)}% of final — ${_whole(revised.overall)}",
                {**facts, **_figures(revised)},
            ),
        ),
        context=(
            CardContext("decided", "Decided", _whole(decided.overall)),
            CardContext("final", "At final", _whole(outcome.at_rate)),
            CardContext(
                "difference",
                "Difference",
                f"{_whole(outcome.difference)} ({outcome.difference_pct}%)",
            ),
        ),
    )
    with _computed(card):
        card_id = await raise_decision_card(
            ctx,
            engagement_id=engagement_id,
            kind=REASSESS_KIND,
            question_key=f"materiality.reassess.{standing.benchmark_key}",
            work_item_id=work_item,
        )
    return ReassessmentRaised(card_id, outcome)


async def _apply_reassessment(tx: UnitOfWork, ctx: AuthContext, decided: AppliedDecision) -> None:
    """The `materiality_reassessment` applier: No change copies the standing thresholds as
    "Reassessed" with the final facts; Revise writes the final-basis thresholds as "Revised" with
    the code-computed impact list, and tells the impacted preparers (AC3.6, AC3.7)."""
    if decided.work_item_id is None:
        raise DomainInvalid(facts={"field": "work_item_id"})
    figures = dict(decided.figures)
    versions = await _locked_versions(tx, decided.work_item_id)
    standing = in_force(versions)
    if standing is None or str(standing.version_no) != figures.get("standing_version"):
        raise MaterialityRecordMoved
    revise = decided.option_key == "revise"
    reassessment: dict[str, object] = {
        "final_amount": figures["final_amount"],
        "at_rate": figures["at_rate"],
        "difference": figures["difference"],
        "difference_pct": figures["difference_pct"],
        "conclusion": "revised" if revise else "no_change",
        "final_period_end": figures["final_period_end"],
    }
    scope = Scope(engagement_id=decided.engagement_id, work_item_id=decided.work_item_id)
    impacted: list[Impacted] = []
    if revise:
        thresholds = _from_figures(figures)
        impacted = await impact_of(ctx.tenant, decided.work_item_id)
        row = next(
            (dict(b) for b in standing.benchmarks if b.get("key") == standing.benchmark_key),
            {"key": standing.benchmark_key, "label": standing.benchmark_key, "use": "overall"},
        )
        row.update(
            amount=figures["benchmark_amount"],
            period_end=figures["final_period_end"],
            tb_id=figures["final_tb_id"],
            layer="final",
        )
        version = await _insert(
            tx,
            ctx,
            decided.work_item_id,
            decided.engagement_id,
            status="revised",
            thresholds=thresholds,
            basis="final",
            tb_id=UUID(figures["final_tb_id"]),
            benchmarks=[row],
            policy_version_id=standing.policy_version_id,
            card_id=decided.card_id,
            decision_id=decided.decision_id,
            reassessment=reassessment,
            impact={
                "items": [
                    {
                        "workpaper_code": i.workpaper_code,
                        "title": i.title,
                        "reason": i.reason,
                        "preparer_user_id": str(i.preparer_user_id)
                        if i.preparer_user_id
                        else None,
                    }
                    for i in impacted
                ]
            },
        )
    else:
        version = await _insert(
            tx,
            ctx,
            decided.work_item_id,
            decided.engagement_id,
            status="reassessed",
            thresholds=thresholds_of(standing),
            basis=standing.basis,
            tb_id=standing.tb_snapshot_id,
            benchmarks=list(standing.benchmarks),
            policy_version_id=standing.policy_version_id,
            card_id=decided.card_id,
            decision_id=decided.decision_id,
            reassessment=reassessment,
        )
    tx.record(
        "materiality_version.revised" if revise else "materiality_version.reassessed",
        target=Target("materiality_version", version),
        after=Ref(decision=decided.decision_id),
        scope=scope,
    )
    tx.emit(
        MaterialityReassessed(
            version_id=version,
            engagement_id=decided.engagement_id,
            work_item_id=decided.work_item_id,
            decision_id=decided.decision_id,
            revised=revise,
        )
    )
    preparers = sorted({i.preparer_user_id for i in impacted if i.preparer_user_id is not None})
    if revise and preparers:
        tx.emit(
            MaterialityRevised(
                version_id=version,
                engagement_id=decided.engagement_id,
                by_user=ctx.user_id,
                recipient_user_ids=preparers,
            )
        )


def register() -> None:
    """The two kinds, reserved to the engagement partner with the matrix's fresh second factor
    and a rationale (C3 refuses a decide without one)."""
    register_decision_kind(
        DecisionKind(
            code=PROPOSE_KIND,
            reserved_role="engagement_partner",
            options=_provided,
            questions={"materiality": "Planning materiality"},
            apply=_apply_decision,
        )
    )
    register_decision_kind(
        DecisionKind(
            code=REASSESS_KIND,
            reserved_role="engagement_partner",
            options=_provided,
            questions={"materiality.reassess": "Materiality at the final basis"},
            apply=_apply_reassessment,
        )
    )


AUDIT_KINDS = frozenset({"materiality_version"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `materiality_version` rows named by an audit event: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(MaterialityVersion.id, MaterialityVersion.engagement_id).where(
                MaterialityVersion.id.in_(list(ids))
            )
        )
        return {found: owned for found, owned in rows}
