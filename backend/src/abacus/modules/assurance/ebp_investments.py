"""EBP-06: investments, certification and trust tie-out (A-05-T39; A-05 F6; DEC-2305).

Lines by layer come from the ledger (C9 and C8: A-06's adjustments feed the AJE, RJE and Final
layers; `layer_unavailable` until they register). Trust lines agree to the TB by code
(`compute.ebp.trust_agreement`). Each certification point's answer is a person's event (0665's
CHECK); a sign-off on the paper waits until every point is evaluated (`certification_unevaluated`).
The routes have authorised the action and the flag.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance.compute.ebp import trust_agreement
from abacus.modules.engagements.api import assurance_item
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.api import engagement_trial_balances, trial_balance_view

KIND: Final = "ebp_investments"
UNEVALUATED: Final = "certification_unevaluated"
POINT_KEYS: Final = (
    "qualifying_institution",
    "complete_and_accurate",
    "period",
    "signer_and_date",
    "covers",
    "not_covered",
)
_ZERO: Final = Decimal(0)
JsonRow = dict[str, Any]  # Any: rows from the database


class NoTrustReport(DomainConflict):
    """No adopted trust lines yet: the point cannot be evaluated against nothing."""

    code = "trust_report_missing"


@dataclass(frozen=True)
class Point:
    key: str
    id: UUID | None
    proposed_answer: str | None
    citation_id: UUID | None
    answer: str
    note: str | None


@dataclass(frozen=True)
class InvestmentsView:
    layer: str
    agreement: trust_agreement.Agreement
    extra: tuple[tuple[str, str, Decimal], ...]  # TB lines outside the trust report (receivable)
    net_assets: Decimal
    tb_balanced: bool
    points: tuple[Point, ...]
    unevaluated: int


def _at_layer(line: Any, layer: str) -> Decimal:  # noqa: ANN401  # Any: the ledger's TbLine
    if layer == "unadjusted":
        return cast(Decimal, line.eoy)
    if layer == "aje":
        return cast(Decimal, line.eoy + (line.aje or _ZERO))
    if layer == "rje":
        return cast(Decimal, line.eoy + (line.rje or _ZERO))
    return cast(Decimal, line.final if line.final is not None else line.eoy)


async def _trust_lines(tenant: TenantContext, work_item_id: UUID) -> list[trust_agreement.TrustLine]:
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT line_key, fund_name, boy, eoy, fair_value_level "
                        "FROM ebp_trust_report_lines "
                        "WHERE work_item_id = :w AND superseded_by IS NULL ORDER BY line_key"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .all()
        )
    return [
        trust_agreement.TrustLine(
            r["line_key"], r["fund_name"], r["boy"], r["eoy"], r["fair_value_level"]
        )
        for r in rows
    ]


async def points(tenant: TenantContext, work_item_id: UUID) -> tuple[Point, ...]:
    """Every point in the rule's order, with its newest evaluation; a missing one is unevaluated."""
    async with tenant_session(tenant) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT DISTINCT ON (p.point_key) p.id, p.point_key, p.proposed_answer, "
                        "p.citation_id, e.answer, e.note FROM ebp_certification_points p "
                        "LEFT JOIN ebp_certification_evaluations e ON e.tenant_id = p.tenant_id "
                        "AND e.point_id = p.id WHERE p.work_item_id = :w "
                        "ORDER BY p.point_key, p.created_at DESC, e.created_at DESC NULLS LAST"
                    ),
                    {"w": work_item_id},
                )
            )
            .mappings()
            .all()
        )
    by_key = {r["point_key"]: r for r in rows}
    out: list[Point] = []
    for key in POINT_KEYS:
        row = by_key.get(key)
        out.append(
            Point(
                key,
                row["id"] if row else None,
                row["proposed_answer"] if row else None,
                row["citation_id"] if row else None,
                (row["answer"] if row else None) or "not_evaluated",
                row["note"] if row else None,
            )
        )
    return tuple(out)


async def investments(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID, layer: str
) -> InvestmentsView:
    tbs = await engagement_trial_balances(tenant, engagement_id)
    if not tbs:
        raise NotFound("trial_balance")
    current = max(tbs, key=lambda t: t.period_end)
    view = await trial_balance_view(tenant, engagement_id, current.id, layer=layer)
    figures = [
        trust_agreement.TbFigure(line.account_name, line.boy, _at_layer(line, layer))
        for line in view.lines
    ]
    trust = await _trust_lines(tenant, work_item_id)
    agreement = trust_agreement.agree(trust, figures)
    names = {trust_agreement.normalised(t.fund_name) for t in trust}
    extra = tuple(
        (line.account_code, line.account_name, _at_layer(line, layer))
        for line in view.lines
        if trust_agreement.normalised(line.account_name) not in names
        and "receivable" in line.account_name.lower()
    )
    total = (
        sum((a.tb_eoy or _ZERO for a in agreement.lines), _ZERO)
        + sum((amount for _, _, amount in extra), _ZERO)
    )
    found = await points(tenant, work_item_id)
    return InvestmentsView(
        layer,
        agreement,
        extra,
        total,
        view.eoy.balanced,
        found,
        sum(1 for p in found if p.answer != "evaluated"),
    )


async def evaluate_point(
    ctx: AuthContext, work_item_id: UUID, point_key: str, answer: str, note: str | None
) -> UUID:
    """A person's evaluation of one point, an insert-only event (0665: human, the transaction's)."""
    if point_key not in POINT_KEYS:
        raise NotFound("ebp_certification_point")
    item = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant, ctx.actor) as tx:
        point = (
            await tx.session.execute(
                text(
                    "SELECT id FROM ebp_certification_points WHERE work_item_id = :w "
                    "AND point_key = :k ORDER BY created_at DESC LIMIT 1"
                ),
                {"w": work_item_id, "k": point_key},
            )
        ).scalar_one_or_none()
        if point is None:
            raise NoTrustReport
        event = (
            await tx.session.execute(
                text(
                    "INSERT INTO ebp_certification_evaluations (tenant_id, engagement_id, "
                    "work_item_id, point_id, answer, note) VALUES (:t, :e, :w, :p, :a, :n) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": item.engagement_id,
                    "w": work_item_id,
                    "p": point,
                    "a": answer,
                    "n": note,
                },
            )
        ).scalar_one()
        tx.record(
            "ebp.certification.point_evaluated",
            target=Target("ebp_certification_point", point),
            after=Ref(event=event, answer=answer),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
        )
    return cast(UUID, event)


async def sign_off_guard(
    tenant: TenantContext, workpaper_id: UUID, work_item_id: UUID | None
) -> tuple[str, int] | None:
    """EBP-06 signs off once every point is evaluated (fail closed without a work item)."""
    del workpaper_id
    if work_item_id is None:
        return (UNEVALUATED, len(POINT_KEYS))
    left = sum(1 for p in await points(tenant, work_item_id) if p.answer != "evaluated")
    return None if left == 0 else (UNEVALUATED, left)


AUDIT_KINDS: Final = frozenset({"ebp_certification_point"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For a certification point an audit event names: id -> the owning engagement."""
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text("SELECT id, engagement_id FROM ebp_certification_points WHERE id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}
