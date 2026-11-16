"""AUD-12's three test variants on A-05's shared attribute grid (A-08-T14; A-08 §3 F2; AUD-12;
DEC-5306; amber).

- **Variants.** `je_testing` (`aud12_je`), `test_of_details` (`aud12_tod`) and `test_of_controls`
  (`aud12_toc`) are grids over one approved sample; a variant swap is a new test of the other
  variant over the same sample version and attributes (the old one stays, insert-only results).
- **Marks** are the grid's (`attribute_grid.mark`): a person's pass, exception or no effect, with
  C4 citations on the item; an agent may only pre-test (`agent_tested` / `needs_human`).
- **The deviation log** (`control_deviations`, 0930, insert-only): a person logs a deviation or
  exception on a tested item. Code decides a difference strictly below clearly trivial is a
  `difference`, logged and never an exception (JE-26-17994's $1,246.85); an exception may be
  routed to a finding (`assurance.api.record_finding`, AUD-15) in the same act, its id kept on the
  row; SHL-15's issue draft is the grid's `exception_prefill`.
- **UDL** (`deviation_log`): the exact upper deviation limit at the firm's confidence (90% unless
  stated) over the items tested (0 of 25 reads 8.8%), by code (`compute.attribute_stats`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.workpapers import attribute_grid as grid
from abacus.modules.workpapers.compute.attribute_stats import (
    below_clearly_trivial,
    upper_deviation_limit,
)

TestKind = Literal["je_testing", "test_of_details", "test_of_controls"]
VARIANT_OF: Final[dict[TestKind, grid.Variant]] = {
    "je_testing": "aud12_je",
    "test_of_details": "aud12_tod",
    "test_of_controls": "aud12_toc",
}
DEFAULT_CONFIDENCE: Final = Decimal("0.90")
DEVIATION: Final = "control_deviation"
# A finding raised from a deviation is recorded by assurance, which registers this at its api
# import (workpapers never imports assurance, ADR-008): (ctx, work item, workpaper, title,
# control deficiency or misstatement, the difference) -> the finding's id.
FindingRaiser = Callable[
    [AuthContext, UUID, UUID, str, Literal["control_deficiency", "misstatement"], Decimal | None],
    Awaitable[UUID],
]
_raisers: list[FindingRaiser] = []
_COUNTS: Final = text(
    "SELECT count(DISTINCT sample_item_id) FILTER (WHERE kind <> 'difference'), count(*) "
    "FROM control_deviations WHERE work_item_id = :w"
)


def register_finding_raiser(raiser: FindingRaiser) -> None:
    _raisers[:] = [raiser]


async def deviation_counts(tenant: TenantContext, work_item_id: UUID) -> tuple[int, int]:
    """(items with a deviation or exception, every logged row) on the work item's tests."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_COUNTS, {"w": work_item_id})).first()
    return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)


MARK: Final = "attribute_test.mark"


class NotAnAud12Test(NotFound):
    pass


class DeviationInvalid(DomainInvalid):
    code = "deviation_invalid"


class SameVariant(DomainConflict):
    code = "same_variant"


@dataclass(frozen=True)
class DeviationRow:
    id: UUID
    sample_item_id: UUID
    attribute_key: str
    kind: Literal["deviation", "exception", "difference"]
    description: str
    difference: Decimal | None
    below_ct: bool
    finding_id: UUID | None
    recorded_by: UUID
    at: datetime


@dataclass(frozen=True)
class DeviationLog:
    test_id: UUID
    rows: tuple[DeviationRow, ...]
    tested: int
    deviations: int  # deviations and exceptions; a below-CT difference is not one
    confidence: Decimal
    udl_pct: Decimal


_TEST = text(
    "SELECT id, engagement_id, work_item_id, workpaper_id, variant, sample_set_id, "
    "sample_set_version, attributes FROM attribute_tests WHERE id = :id"
)
_INSERT = text(
    "INSERT INTO control_deviations (tenant_id, engagement_id, work_item_id, test_id, "
    "sample_item_id, attribute_key, kind, description, difference, below_ct, finding_id, "
    "recorded_by, actor_kind) VALUES (:t, :e, :w, :test, :item, :key, :kind, :d, :diff, :ct, "
    ":f, :u, 'human') RETURNING id"
)
_LOG = text(
    "SELECT id, sample_item_id, attribute_key, kind, description, difference, below_ct, "
    "finding_id, recorded_by, at FROM control_deviations WHERE test_id = :id ORDER BY at, id"
)


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def _aud12(ctx: AuthContext, test_id: UUID) -> dict[str, object]:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_TEST, {"id": test_id})).mappings().first()
    if row is None or row["variant"] not in VARIANT_OF.values():
        raise NotAnAud12Test("attribute_test")
    from abacus.modules.engagements.api import engagement_resource_of

    await authorise(
        ctx, MARK, await engagement_resource_of(ctx.tenant, cast(UUID, row["engagement_id"]))
    )
    return dict(row)


async def create_variant_test(
    ctx: AuthContext,
    *,
    kind: TestKind,
    engagement_id: UUID,
    work_item_id: UUID,
    workpaper_id: UUID,
    sample_set_id: UUID,
    sample_version: int,
    attributes: list[grid.Attribute],
) -> UUID:
    return await grid.create_test(
        ctx,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        workpaper_id=workpaper_id,
        variant=VARIANT_OF[kind],
        sample_set_id=sample_set_id,
        sample_version=sample_version,
        attributes=attributes,
    )


async def swap_variant(ctx: AuthContext, test_id: UUID, to: TestKind) -> UUID:
    """The same sample and attributes under the other variant (AUD-12's variant switch)."""
    _human(ctx, MARK)
    row = await _aud12(ctx, test_id)
    if row["variant"] == VARIANT_OF[to]:
        raise SameVariant(facts={"variant": str(row["variant"])})
    attributes = [
        grid.Attribute(key=str(a["key"]), label=str(a["label"]))
        for a in cast("list[dict[str, object]]", row["attributes"])
    ]
    return await create_variant_test(
        ctx,
        kind=to,
        engagement_id=cast(UUID, row["engagement_id"]),
        work_item_id=cast(UUID, row["work_item_id"]),
        workpaper_id=cast(UUID, row["workpaper_id"]),
        sample_set_id=cast(UUID, row["sample_set_id"]),
        sample_version=cast(int, row["sample_set_version"]),
        attributes=attributes,
    )


async def log_deviation(
    ctx: AuthContext,
    test_id: UUID,
    *,
    sample_item_id: UUID,
    attribute_key: str,
    description: str,
    difference: Decimal | None = None,
    clearly_trivial: Decimal | None = None,
    raise_finding: bool = False,
    finding_title: str | None = None,
) -> DeviationRow:
    """A person logs a deviation or exception; code decides a below-CT difference is not one."""
    _human(ctx, MARK)
    row = await _aud12(ctx, test_id)
    if not description.strip() or len(description) > 1000:
        raise DeviationInvalid(facts={"field": "description"})
    keys = {str(a["key"]) for a in cast("list[dict[str, object]]", row["attributes"])}
    if attribute_key not in keys:
        raise DeviationInvalid(facts={"field": "attribute_key"})
    below = (
        difference is not None
        and clearly_trivial is not None
        and below_clearly_trivial(difference, clearly_trivial)
    )
    if below:
        kind: Literal["deviation", "exception", "difference"] = "difference"
    elif row["variant"] == VARIANT_OF["test_of_controls"]:
        kind = "deviation"
    else:
        kind = "exception"
    finding_id: UUID | None = None
    if raise_finding:
        if kind == "difference":
            raise DeviationInvalid(facts={"field": "below_clearly_trivial"})
        if not _raisers:
            raise RuntimeError("no finding raiser registered (assurance.api)")
        finding_id = await _raisers[0](
            ctx,
            cast(UUID, row["work_item_id"]),
            cast(UUID, row["workpaper_id"]),
            (finding_title or description)[:200],
            "control_deficiency" if kind == "deviation" else "misstatement",
            None if difference is None else Decimal(difference),
        )
    async with uow(ctx.tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT,
                {
                    "t": ctx.tenant_id,
                    "e": row["engagement_id"],
                    "w": row["work_item_id"],
                    "test": test_id,
                    "item": sample_item_id,
                    "key": attribute_key,
                    "kind": kind,
                    "d": description.strip(),
                    "diff": difference,
                    "ct": below,
                    "f": finding_id,
                    "u": ctx.user_id,
                },
            ),
        )
        tx.record(
            "control_deviation.logged",
            target=Target(DEVIATION, made),
            after=Ref(test_id=test_id, below_ct=int(below)),
        )
    log = await deviation_log(ctx, test_id)
    return next(r for r in log.rows if r.id == made)


async def deviation_log(
    ctx: AuthContext, test_id: UUID, *, confidence: Decimal = DEFAULT_CONFIDENCE
) -> DeviationLog:
    row = await _aud12(ctx, test_id)
    found = await grid.grid(ctx, cast(UUID, row["engagement_id"]), test_id)
    tested = sum(1 for r in found.rows if r.state in ("pass", "exception", "no_effect"))
    async with tenant_session(ctx.tenant) as session:
        rows = tuple(
            DeviationRow(
                id=r["id"],
                sample_item_id=r["sample_item_id"],
                attribute_key=r["attribute_key"],
                kind=r["kind"],
                description=r["description"],
                difference=r["difference"],
                below_ct=r["below_ct"],
                finding_id=r["finding_id"],
                recorded_by=r["recorded_by"],
                at=r["at"],
            )
            for r in (await session.execute(_LOG, {"id": test_id})).mappings()
        )
    deviations = len({(r.sample_item_id) for r in rows if r.kind != "difference"})
    size = max(tested, deviations, 1)
    return DeviationLog(
        test_id=test_id,
        rows=rows,
        tested=tested,
        deviations=deviations,
        confidence=confidence,
        udl_pct=upper_deviation_limit(min(deviations, size), size, confidence),
    )
