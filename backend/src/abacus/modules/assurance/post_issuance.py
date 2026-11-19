"""Post-issuance cases (Q-05-T12; S51 partials, TASK-8730; DEC-5724; SPEC-711 AC-15 to AC-18;
AUD-30). RED path (protected): it writes past `archived_guard()` under the `post_issuance` kind.

- **Open** a case on an archived audit only (409 `not_archived` before lock): type, source and
  description (sealed), `PI-nn`; the engagement partners are told.
- **Compare** (code, ADR-050): the corrected figures against A-05's certified trust-report lines
  by line key; no matching line, no comparison (`comparison_unavailable`, DV-9). The evaluation
  measures the total difference against the materiality in force at release (`ct`, `overall`),
  computed by `compute.post_issuance`, never typed.
- **Decide**: the engagement partner, fresh MFA, human-only, on the case row itself. The audit is
  locked: its decision cards are behind the guard, and the case row is the table the
  `post_issuance` kind reaches (ADR P-43). The options are code's; "no_action" carries the agent
  recommendation tag only when the difference is below clearly trivial and no disclosure is
  affected. Nothing else in the locked work item changes.

Every read authorises `post_issuance.read` on the work item (walls 404). The agent never opens,
compares or decides (matrix `agent: deny`; the decision CHECK on `app.actor_kind`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance.compute import post_issuance as calc
from abacus.modules.assurance.events import PostIssuanceCaseOpened
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, authorise, engagement_partners

TARGET: Final = "post_issuance_event"
_FINGERPRINT: Final = "assurance.post_issuance"
CaseType = Literal["subsequent_fact", "omitted_procedure", "reissuance_request"]
Decision = calc.Option
STANDARD: Final[Mapping[str, str | None]] = {
    "subsequent_fact": "au_c_560",
    "omitted_procedure": "au_c_585",
    "reissuance_request": None,
}


class NotArchived(DomainConflict):
    code = "not_archived"


class ComparisonUnavailable(DomainConflict):
    code = "comparison_unavailable"


class CaseDecided(DomainConflict):
    code = "post_issuance_case_decided"


@dataclass(frozen=True)
class ComparedLine:
    line_key: str
    label: str
    as_certified: Decimal
    as_corrected: Decimal
    difference: Decimal


@dataclass(frozen=True)
class CaseEvaluation:
    total_difference: Decimal
    clearly_trivial: Decimal
    overall_materiality: Decimal
    share_pct: Decimal
    below_clearly_trivial: bool
    disclosure_affected: bool
    materiality_version_id: UUID


@dataclass(frozen=True)
class Case:
    case_id: UUID
    work_item_id: UUID
    ref: str
    type: CaseType
    standard: str | None
    source_kind: str
    source_evidence_version_id: UUID | None
    received_at: datetime
    description: str
    status: str
    decision: str | None
    decided_by: UUID | None
    decided_at: datetime | None
    comparison: tuple[ComparedLine, ...]
    evaluation: CaseEvaluation | None
    options: tuple[str, ...]
    recommended: str | None


async def _resource_for(ctx: AuthContext, action: str, work_item_id: UUID) -> UUID:
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, replace(ref.resource(), work_item_id=work_item_id))
    return engagement_id


_CASES = text(
    "SELECT id, work_item_id, ref, type, standard, source_kind, source_evidence_version_id, "
    "received_at, description_sealed, status, decision, decided_by, decided_at "
    "FROM post_issuance_events WHERE work_item_id = :w "
    "AND (CAST(:id AS uuid) IS NULL OR id = :id) ORDER BY ref"
)
_COMPARED = text(
    "SELECT c.event_id, c.line_key, coalesce(t.fund_name, c.line_key), c.as_certified, "
    "c.as_corrected, c.difference FROM post_issuance_comparisons c "
    "JOIN post_issuance_events e ON e.id = c.event_id "
    "LEFT JOIN ebp_trust_report_lines t ON t.work_item_id = e.work_item_id "
    "AND t.line_key = c.line_key AND t.superseded_by IS NULL "
    "WHERE e.work_item_id = :w ORDER BY c.line_key"
)
_EVALUATED = text(
    "SELECT v.event_id, v.total_difference, v.clearly_trivial, v.overall_materiality, "
    "v.share_pct, v.below_clearly_trivial, v.disclosure_affected, v.materiality_version_id "
    "FROM post_issuance_evaluations v JOIN post_issuance_events e ON e.id = v.event_id "
    "WHERE e.work_item_id = :w"
)


async def _read(ctx: AuthContext, work_item_id: UUID, case_id: UUID | None) -> list[Case]:
    async with tenant_session(ctx.tenant) as session:
        rows = [
            tuple(r) for r in await session.execute(_CASES, {"w": work_item_id, "id": case_id})
        ]
        compared = [tuple(r) for r in await session.execute(_COMPARED, {"w": work_item_id})]
        evaluated = {
            r[0]: tuple(r) for r in await session.execute(_EVALUATED, {"w": work_item_id})
        }
    out: list[Case] = []
    for r in rows:
        cid = cast(UUID, r[0])
        lines = tuple(
            ComparedLine(str(c[1]), str(c[2]), *(cast(Decimal, v) for v in c[3:6]))
            for c in compared
            if c[0] == cid
        )
        ev = evaluated.get(cid)
        evaluation = (
            None
            if ev is None
            else CaseEvaluation(
                cast(Decimal, ev[1]), cast(Decimal, ev[2]), cast(Decimal, ev[3]),
                cast(Decimal, ev[4]), bool(ev[5]), bool(ev[6]), cast(UUID, ev[7]),
            )
        )  # fmt: skip
        offered: tuple[str, ...] = ()
        recommended: str | None = None
        if evaluation is not None:
            computed = calc.options(
                calc.Evaluation(
                    evaluation.total_difference,
                    evaluation.clearly_trivial,
                    evaluation.overall_materiality,
                    evaluation.share_pct,
                    evaluation.below_clearly_trivial,
                ),
                disclosure_affected=evaluation.disclosure_affected,
            )
            offered, recommended = computed.options, computed.recommended
        description = (await open_sealed(ctx.tenant_id, cast(bytes, r[8]), _FINGERPRINT)).decode()
        out.append(
            Case(
                cid, cast(UUID, r[1]), str(r[2]), cast(CaseType, r[3]),
                cast(str | None, r[4]), str(r[5]), cast(UUID | None, r[6]),
                cast(datetime, r[7]), description, str(r[9]), cast(str | None, r[10]),
                cast(UUID | None, r[11]), cast(datetime | None, r[12]), lines, evaluation,
                offered, recommended,
            )
        )  # fmt: skip
    return out


async def cases(ctx: AuthContext, work_item_id: UUID) -> list[Case]:
    await _resource_for(ctx, "post_issuance.read", work_item_id)
    return await _read(ctx, work_item_id, None)


async def case(ctx: AuthContext, work_item_id: UUID, case_id: UUID) -> Case:
    await _resource_for(ctx, "post_issuance.read", work_item_id)
    found = await _read(ctx, work_item_id, case_id)
    if not found:
        raise NotFound(TARGET)
    return found[0]


_LOCKED = text("SELECT created_at FROM archives WHERE engagement_id = :e")


async def archive_locked_at(tenant: TenantContext, engagement_id: UUID) -> datetime | None:
    async with tenant_session(tenant) as session:
        return cast(datetime | None, await session.scalar(_LOCKED, {"e": engagement_id}))


_NEXT_REF = text("SELECT count(*) + 1 FROM post_issuance_events")
_INSERT = text(
    "INSERT INTO post_issuance_events (tenant_id, engagement_id, work_item_id, ref, type, "
    "standard, source_kind, received_at, description_sealed, created_by, "
    "source_evidence_version_id) VALUES (:t, :e, :w, :ref, :type, :std, :src, clock_timestamp(), "
    ":d, :u, :ev) RETURNING id"
)


async def open_case(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    type: CaseType,  # the contract's field name
    source_kind: str,
    description: str,
    source_evidence_version_id: UUID | None = None,
) -> Case:
    """AUD-30 f: managers and the EP open a case, on an archived audit only."""
    engagement_id = await _resource_for(ctx, "post_issuance.create", work_item_id)
    if await archive_locked_at(ctx.tenant, engagement_id) is None:
        raise NotArchived(facts={"work_item_id": str(work_item_id)})
    if not description.strip():
        raise DomainInvalid(facts={"field": "description"})
    sealed = await seal(ctx.tenant_id, description.strip().encode(), _FINGERPRINT)
    partners = await engagement_partners(ctx.tenant_id, engagement_id)
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext('post_issuance_ref:' || :t))"),
            {"t": str(ctx.tenant_id)},
        )
        number = int(cast(int, await tx.session.scalar(_NEXT_REF)))
        case_id = cast(
            UUID,
            await tx.session.scalar(
                _INSERT,
                {
                    "t": ctx.tenant_id, "e": engagement_id, "w": work_item_id,
                    "ref": f"PI-{number:02d}", "type": type, "std": STANDARD[type],
                    "src": source_kind, "d": sealed, "u": ctx.user_id,
                    "ev": source_evidence_version_id,
                },
            ),
        )  # fmt: skip
        tx.record(
            "post_issuance.case_opened",
            target=Target(TARGET, case_id),
            after=Ref(number=number),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            PostIssuanceCaseOpened(
                case_id=case_id,
                work_item_id=work_item_id,
                by_user=ctx.user_id,
                recipient_user_ids=partners,
            )
        )
    return await case(ctx, work_item_id, case_id)


_CERTIFIED = text(
    "SELECT line_key, eoy FROM ebp_trust_report_lines WHERE work_item_id = :w "
    "AND superseded_by IS NULL AND eoy IS NOT NULL"
)
_MATERIALITY = text(
    "SELECT id, ct, overall FROM materiality_versions WHERE work_item_id = :w "
    "AND status IN ('decided', 'revised', 'reassessed') "
    "AND computed_at <= coalesce((SELECT min(released_at) FROM report_releases "
    "WHERE work_item_id = :w), clock_timestamp()) ORDER BY version_no DESC LIMIT 1"
)
_HAS_COMPARISON = text(
    "SELECT EXISTS (SELECT 1 FROM post_issuance_comparisons WHERE event_id = :c)"
)


async def compare_case(
    ctx: AuthContext,
    work_item_id: UUID,
    case_id: UUID,
    corrected: Mapping[str, Decimal],
    *,
    disclosure_affected: bool = False,
) -> Case:
    """The code's comparison and evaluation (AC-15). `corrected` is the corrected certification's
    figures by line key (the parser's output, or the figures attached when it cannot match;
    DV-9). Only matching certified lines compare; none matching is `comparison_unavailable`.
    Once compared, a case keeps its comparison (insert-only)."""
    engagement_id = await _resource_for(ctx, "post_issuance.analyse", work_item_id)
    found = await case(ctx, work_item_id, case_id)
    if found.status == "decided":
        raise CaseDecided(facts={"case_id": str(case_id)})
    async with tenant_session(ctx.tenant) as session:
        certified = {str(r[0]): cast(Decimal, r[1]) for r in await session.execute(
            _CERTIFIED, {"w": work_item_id}
        )}  # fmt: skip
        materiality = (await session.execute(_MATERIALITY, {"w": work_item_id})).first()
        compared_already = bool(await session.scalar(_HAS_COMPARISON, {"c": case_id}))
    if compared_already:
        return found
    lines = calc.compare(
        [
            calc.LineIn(key, key, certified[key], Decimal(amount))
            for key, amount in sorted(corrected.items())
            if key in certified
        ]
    )
    if not lines or materiality is None:
        raise ComparisonUnavailable(facts={"case_id": str(case_id)})
    total = sum((ln.difference for ln in lines), Decimal(0))
    evaluation = calc.evaluate(
        total,
        clearly_trivial=cast(Decimal, materiality[1]),
        overall_materiality=cast(Decimal, materiality[2]),
    )
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        for ln in lines:
            await tx.session.execute(
                text(
                    "INSERT INTO post_issuance_comparisons (tenant_id, event_id, line_key, "
                    "as_certified, as_corrected, difference) VALUES (:t, :c, :k, :a, :b, :d)"
                ),
                {"t": ctx.tenant_id, "c": case_id, "k": ln.line_key, "a": ln.as_certified,
                 "b": ln.as_corrected, "d": ln.difference},
            )  # fmt: skip
        await tx.session.execute(
            text(
                "INSERT INTO post_issuance_evaluations (tenant_id, event_id, total_difference, "
                "clearly_trivial, overall_materiality, share_pct, below_clearly_trivial, "
                "disclosure_affected, materiality_version_id) VALUES (:t, :c, :td, :ct, :om, "
                ":sp, :below, :disc, :mv)"
            ),
            {"t": ctx.tenant_id, "c": case_id, "td": evaluation.total_difference,
             "ct": evaluation.clearly_trivial, "om": evaluation.overall_materiality,
             "sp": evaluation.share_pct, "below": evaluation.below_clearly_trivial,
             "disc": disclosure_affected, "mv": materiality[0]},
        )  # fmt: skip
        await tx.session.execute(
            text(
                "UPDATE post_issuance_events SET status = 'awaiting_decision' "
                "WHERE id = :c AND status IN ('open', 'analysing')"
            ),
            {"c": case_id},
        )
        tx.record(
            "post_issuance.compared",
            target=Target(TARGET, case_id),
            after=Ref(lines=len(lines)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await case(ctx, work_item_id, case_id)


async def require_comparison(ctx: AuthContext, work_item_id: UUID, case_id: UUID) -> Case:
    """The analysis is offered only once the code has compared (409 `comparison_unavailable`)."""
    found = await case(ctx, work_item_id, case_id)
    if not found.comparison or found.evaluation is None:
        raise ComparisonUnavailable(facts={"case_id": str(case_id)})
    return found


_DECIDE = text(
    "UPDATE post_issuance_events SET status = 'decided', decision = :d, decided_by = :u, "
    "decided_at = clock_timestamp(), rationale_sealed = :r, "
    "decided_actor_kind = current_setting('app.actor_kind', true) "
    "WHERE id = :c AND status = 'awaiting_decision' AND decision IS NULL RETURNING id"
)


async def decide(
    ctx: AuthContext, work_item_id: UUID, case_id: UUID, *, decision: str, rationale: str
) -> Case:
    """The engagement partner decides among the code's options, with a rationale (fresh MFA by
    the matrix; human-only by the CHECK). 409 `comparison_unavailable` before the comparison,
    `post_issuance_case_decided` once decided."""
    engagement_id = await _resource_for(ctx, "post_issuance.decide", work_item_id)
    found = await require_comparison(ctx, work_item_id, case_id)
    if found.decision is not None:
        raise CaseDecided(facts={"case_id": str(case_id)})
    if decision not in found.options:
        raise DomainInvalid(facts={"field": "decision"})
    if not rationale.strip():
        raise DomainInvalid(facts={"field": "rationale"})
    sealed = await seal(ctx.tenant_id, rationale.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        moved = await tx.session.scalar(
            _DECIDE, {"d": decision, "u": ctx.user_id, "r": sealed, "c": case_id}
        )
        if moved is None:
            raise CaseDecided(facts={"case_id": str(case_id)})
        tx.record(
            "post_issuance.decided",
            target=Target(TARGET, case_id),
            after=Ref(option=found.options.index(decision)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await case(ctx, work_item_id, case_id)


__all__ = [
    "Case",
    "CaseDecided",
    "CaseEvaluation",
    "ComparedLine",
    "ComparisonUnavailable",
    "NotArchived",
    "archive_locked_at",
    "case",
    "cases",
    "compare_case",
    "decide",
    "open_case",
    "require_comparison",
]
