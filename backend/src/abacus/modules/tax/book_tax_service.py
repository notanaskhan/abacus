"""The book-tax service (T-06-T34; TASK-8832; T-06 F2; SPEC-702; TXP-04 a, b, c; ADR-050; DEC-77,
DEC-5834). Amber.

- **M-3** (`m3`): Parts II and III from the return's `book_tax_items` (schedules `m3_part2`,
  `m3_part3`), each row (a) + (b) + (c) = (d) (the table's CHECK and E4's), with the requirement
  computed by E4 from book total assets on the TB (total assets of $10 million or more require it;
  under $50 million the M-1 may stand in for Parts II and III). Filed when required.
- **M-1** (`m1`): the reference reconciliation from the same rows (net income per books, then
  each difference as an addition or a subtraction), filed only when the M-3 is not required: the
  M-1 is never filed beside an M-3.
- **M-2** stays T-05's `GET …/schedules/m2` with its `variant` (`as_drafted`, `with_fix`): the With
  proposed fix view previews the 6,200 change set's effect without writing, and approving or
  rejecting that change set is C3's (`POST /v1/proposals/{id}:approve|:reject` with
  `seen_version`; a stale version answers 409 `proposal_changed`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.tax.compute import book_tax as e4

READ: Final = "book_tax.read"
ZERO: Final = Decimal(0)

_ROWS: Final = text(
    "SELECT schedule, line_key, description, col_a, col_b, col_c, col_d, kind FROM book_tax_items "
    "WHERE work_item_id = :r ORDER BY schedule, line_key, id"
)


@dataclass(frozen=True)
class Row:
    schedule: str
    line: str
    label: str
    a: Decimal
    b: Decimal
    c: Decimal
    d: Decimal
    kind: str


@dataclass(frozen=True)
class Schedule:
    schedule: Literal["m3", "m1"]
    required: bool
    total_assets: Decimal
    book_income: Decimal
    rows: tuple[Row, ...]
    filed: bool


async def rows_of(tenant: TenantContext, return_id: UUID) -> list[Row]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_ROWS, {"r": return_id})).all()
    return [
        Row(
            str(r.schedule),
            str(r.line_key),
            str(r.description),
            Decimal(r.col_a),
            Decimal(r.col_b),
            Decimal(r.col_c),
            Decimal(r.col_d),
            str(r.kind),
        )
        for r in found
    ]


def m3_of(rows: list[Row], total_assets: Decimal) -> Schedule:
    parts = [r for r in rows if r.schedule in ("m3_part2", "m3_part3")]
    e4.reconcile_m3(
        [e4.M3Row(r.label, r.a, r.b, r.c, r.d) for r in parts],
        part_i_line_11=sum((r.a for r in parts), ZERO),
        analysis_line_1=sum((r.d for r in parts), ZERO),
    )  # every row foots or E4 raises
    need = e4.m3_requirement(total_assets)
    return Schedule("m3", need.required, total_assets, sum((r.a for r in parts), ZERO),
                    tuple(parts), need.required)  # fmt: skip


def m1_of(rows: list[Row], total_assets: Decimal) -> Schedule:
    """The M-1 from the same differences: each row's (b) + (c) is an addition when positive and
    a subtraction when negative; explicit `m1` rows are used as they are."""
    own = [r for r in rows if r.schedule == "m1"]
    source = own or [r for r in rows if r.schedule in ("m3_part2", "m3_part3")]
    book = sum((r.a for r in source), ZERO)
    diffs = [r.b + r.c for r in source]
    m1 = e4.m1(book, [x for x in diffs if x > 0], [-x for x in diffs if x < 0])
    need = e4.m3_requirement(total_assets)
    return Schedule("m1", need.required, total_assets, m1.line_1, tuple(source),
                    not need.required)  # fmt: skip


async def total_assets(ctx: AuthContext, return_id: UUID, engagement_id: UUID) -> Decimal:
    from abacus.modules.tax.entity_tb import tb_tallies

    _tallies, figures = await tb_tallies(ctx, return_id, engagement_id)
    found = next((f for f in figures if f.key == "book_total_assets"), None)
    return ZERO if found is None else found.amount


async def schedule(ctx: AuthContext, return_id: UUID, which: Literal["m3", "m1"]) -> Schedule:
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    await authorise(ctx, READ, await return_resource(ctx, loaded))
    rows = await rows_of(ctx.tenant, return_id)
    assets = await total_assets(ctx, return_id, loaded.facts.engagement_id)
    return m3_of(rows, assets) if which == "m3" else m1_of(rows, assets)


__all__ = ["Row", "Schedule", "m1_of", "m3_of", "rows_of", "schedule", "total_assets"]
