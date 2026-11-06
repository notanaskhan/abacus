"""A-06-T13's service half: misstatements, the SUM and its snapshots (AUD-16; DEC-2354).

Code's SUM reads the misstatements a person recorded and the materiality in force, and hands them
to `compute/sum.py`. The browser renders these numbers and computes none. A booked misstatement is
listed beside the SUM, never accumulated; a prior-year carry is context, never accumulated.
Passing a misstatement on the SUM is the engagement partner's act, with a sealed reason (DF-28).
Factors go through `review.api.record_value`; `flagged` is set by code. A snapshot freezes the
totals and factors for the partner's `sum_conclusion` card and A-07's letter.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.assurance.compute import sum as sum_engine
from abacus.modules.assurance.materiality import in_force, versions_of
from abacus.modules.engagements.api import assurance_item
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import current_values, record_value

TARGET: Final = "audit_misstatement"
SUM_TARGET: Final = "sum"
_FINGERPRINT: Final = "audit_misstatement:passed_reason"
VIEWS: Final[Mapping[str, tuple[str, ...]]] = {
    "proposed": ("candidate", "confirmed", "proposed_to_client"),
    "reclass": ("candidate", "confirmed", "proposed_to_client", "booked"),
    "passed": ("passed_on_sum",),
    "below_ct": ("below_ct",),
}
_ACCUMULATED: Final = ("confirmed", "proposed_to_client", "passed_on_sum", "below_ct")
# A factor reading one of these words is flagged by code: the partner sees it before concluding.
_FLAGGED_VALUES: Final = frozenset({"yes", "true", "present", "flagged"})


class NoMateriality(DomainConflict):
    """The SUM measures against a decided materiality; none is in force."""

    code = "nothing_decided"


class NotPassable(DomainConflict):
    """Only a misstatement the client declined to book can be passed on the SUM."""

    code = "misstatement_not_passable"


@dataclass(frozen=True)
class MisstatementRow:
    id: UUID
    ref: str
    origin_ref: str | None
    type: str
    nature: str
    status: str
    amount: Decimal
    finding_ref: str | None
    fs_effect: Mapping[str, Any]  # Any: JSON from the database
    carried_from_py: bool
    py_ref: str | None
    version: int


@dataclass(frozen=True)
class SumView:
    column_set: str
    result: sum_engine.Result
    materiality_version_id: UUID
    overall: Decimal
    pm: Decimal
    ct: Decimal
    label: str
    current: tuple[MisstatementRow, ...]
    prior_year: tuple[MisstatementRow, ...]
    booked: tuple[MisstatementRow, ...]
    below_ct_total: Decimal
    counts: Mapping[str, int] = field(default_factory=dict[str, int])
    factors: tuple[tuple[str, str, bool], ...] = ()


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def effects(row: MisstatementRow) -> tuple[Decimal, Decimal]:
    """(rollover, iron curtain): the record's own signed effects; a record with none states its
    amount under both views."""
    rollover = _dec(row.fs_effect.get("change_in_net_assets"))
    iron = _dec(row.fs_effect.get("net_assets"))
    return (
        rollover if rollover is not None else row.amount,
        iron if iron is not None else row.amount,
    )


async def _rows(tenant: TenantContext, work_item_id: UUID) -> list[MisstatementRow]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT m.*, f.ref AS finding_ref FROM audit_misstatements m "
                "LEFT JOIN audit_findings f ON f.id = m.finding_id "
                "WHERE m.work_item_id = :w ORDER BY m.created_at, m.id"
            ),
            {"w": work_item_id},
        )
        return [
            MisstatementRow(
                r["id"],
                r["ref"],
                r["origin_ref"],
                r["type"],
                r["nature"],
                r["status"],
                Decimal(str(r["amount"])),
                r["finding_ref"],
                r["fs_effect"] or {},
                r["carried_from_py"],
                r["py_ref"],
                r["version"],
            )
            for r in found.mappings()
        ]


async def work_item_of(tenant: TenantContext, misstatement_id: UUID) -> UUID:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text("SELECT work_item_id FROM audit_misstatements WHERE id = :id"),
                {"id": misstatement_id},
            )
        ).scalar()
    if found is None:
        raise NotFound(TARGET)
    return UUID(str(found))


def in_view(row: MisstatementRow, view: str) -> bool:
    if row.carried_from_py:
        return False
    if view == "reclass":
        return row.nature == "reclassification" and row.status in VIEWS["reclass"]
    return row.nature == "misstatement" and row.status in VIEWS[view]


async def misstatements(
    tenant: TenantContext, work_item_id: UUID, view: str
) -> list[MisstatementRow]:
    return [r for r in await _rows(tenant, work_item_id) if in_view(r, view)]


async def _column_set(tenant: TenantContext, work_item_id: UUID) -> str:
    item = await assurance_item(tenant, work_item_id)
    ebp = item.ebp_plan_kind is not None or item.assurance_type.startswith("ebp")
    return "ebp_net_assets" if ebp else "commercial"


async def factors_of(
    tenant: TenantContext, work_item_id: UUID
) -> tuple[tuple[str, str, bool], ...]:
    current = await current_values(tenant, SUM_TARGET, work_item_id)
    return tuple(
        (
            key,
            str(value.get("v", "")),
            str(value.get("v", "")).strip().lower() in _FLAGGED_VALUES,
        )
        for key, value in sorted(current.items())
    )


async def sum_view(tenant: TenantContext, work_item_id: UUID, view: str | None) -> SumView:
    """Code's SUM under the column set the engagement uses (or the one the viewer chose)."""
    column_set = view or await _column_set(tenant, work_item_id)
    decided = in_force(await versions_of(tenant, work_item_id))
    if decided is None:
        raise NoMateriality
    rows = await _rows(tenant, work_item_id)
    current = [
        r
        for r in rows
        if r.nature == "misstatement" and r.status in _ACCUMULATED and not r.carried_from_py
    ]
    prior = [r for r in rows if r.carried_from_py]
    items = [
        sum_engine.Item(
            ref=r.ref,
            rollover=effects(r)[0],
            iron_curtain=effects(r)[1],
            below_ct=r.status == "below_ct",
        )
        for r in current
    ] + [
        sum_engine.Item(
            ref=r.ref, rollover=effects(r)[0], iron_curtain=effects(r)[1], prior_year=True
        )
        for r in prior
    ]
    result = sum_engine.evaluate(
        items,
        sum_engine.Thresholds(
            overall=Decimal(decided.overall), pm=Decimal(decided.pm), ct=Decimal(decided.ct)
        ),
        column_set=column_set,  # pyright: ignore[reportArgumentType] -- checked by the route's Literal
    )
    below = [r for r in current if r.status == "below_ct"]
    return SumView(
        column_set=column_set,
        result=result,
        materiality_version_id=decided.id,
        overall=Decimal(decided.overall),
        pm=Decimal(decided.pm),
        ct=Decimal(decided.ct),
        label=f"v{decided.version_no} · {decided.rate_pct}%",
        current=tuple(r for r in current if r.status != "below_ct"),
        prior_year=tuple(prior),
        booked=tuple(r for r in rows if r.status == "booked" and r.nature == "misstatement"),
        below_ct_total=sum((effects(r)[0] for r in below), Decimal(0)),
        counts={v: sum(1 for r in rows if in_view(r, v)) for v in VIEWS},
        factors=await factors_of(tenant, work_item_id),
    )


async def pass_on_sum(ctx: AuthContext, misstatement_id: UUID, reason: str) -> UUID:
    """DF-28: the partner passes a misstatement the client declined, with a reason. The route
    authorised `misstatement.pass_to_sum` on the engagement. Returns the work item."""
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    text(
                        "SELECT id, work_item_id, engagement_id, status FROM audit_misstatements "
                        "WHERE id = :id FOR UPDATE"
                    ),
                    {"id": misstatement_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound(TARGET)
        if row["status"] not in ("confirmed", "proposed_to_client"):
            raise NotPassable(facts={"status": row["status"]})
        await tx.session.execute(
            text(
                "UPDATE audit_misstatements SET status = 'passed_on_sum', passed_by = :by, "
                "passed_reason_sealed = :why, version = version + 1 WHERE id = :id"
            ),
            {
                "by": ctx.user_id,
                "why": await seal(ctx.tenant_id, reason.encode("utf-8"), _FINGERPRINT),
                "id": misstatement_id,
            },
        )
        tx.record(
            "audit_misstatement.passed_on_sum",
            target=Target(TARGET, misstatement_id),
            after=Ref(by=ctx.user_id),
            scope=Scope(engagement_id=row["engagement_id"], work_item_id=row["work_item_id"]),
        )
    return UUID(str(row["work_item_id"]))


async def record_factor(
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    factor: str,
    value: str,
    note: str | None,
    citation_ids: Sequence[UUID],
) -> None:
    async with uow(ctx.tenant) as tx:
        await record_value(
            tx,
            engagement_id=engagement_id,
            target_type=SUM_TARGET,
            target_id=work_item_id,
            field_key=factor,
            value={"t": "text", "v": value},
            value_source="human",
            cause="edit",
            value_kind="exact",
            citation_ids=citation_ids,
            citation_note=note or "Recorded by the engagement team",
        )
        tx.record(
            "sum.factor_recorded",
            target=Target(SUM_TARGET, work_item_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


async def snapshot(
    ctx: AuthContext, engagement_id: UUID, work_item_id: UUID, purpose: str
) -> tuple[UUID, int, str]:
    """Freezes the totals and factors, insert-only. Returns id, number and inputs hash."""
    found = await sum_view(ctx.tenant, work_item_id, None)
    result = found.result
    totals = {
        "rollover": str(result.rollover),
        "iron_curtain": str(result.iron_curtain),
        "aggregate": str(result.aggregate),
        "pct_of_pm": str(result.pct_of_pm),
        "accumulated": list(result.accumulated),
        "below_ct": list(result.below_ct),
    }
    async with uow(ctx.tenant) as tx:
        number = int(
            (
                await tx.session.execute(
                    text(
                        "SELECT coalesce(max(version_no), 0) + 1 FROM sum_snapshots "
                        "WHERE work_item_id = :w"
                    ),
                    {"w": work_item_id},
                )
            ).scalar_one()
        )
        snapshot_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO sum_snapshots (tenant_id, engagement_id, work_item_id, "
                    "version_no, materiality_version_id, column_set, engine_version, inputs_hash, "
                    "totals, qualitative_factors, purpose, created_by) VALUES (:t, :e, :w, :n, "
                    ":m, :cs, :ev, :h, CAST(:totals AS jsonb), CAST(:factors AS jsonb), :p, :by) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "n": number,
                    "m": found.materiality_version_id,
                    "cs": found.column_set,
                    "ev": result.engine_version,
                    "h": result.inputs_hash,
                    "totals": json.dumps(totals),
                    "factors": json.dumps(
                        [{"factor": k, "value": v, "flagged": f} for k, v, f in found.factors]
                    ),
                    "p": purpose,
                    "by": ctx.user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "sum.snapshot_frozen",
            target=Target(SUM_TARGET, work_item_id),
            after=Ref(version=number, inputs_hash=result.inputs_hash),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return UUID(str(snapshot_id)), number, result.inputs_hash
