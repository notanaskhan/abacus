"""Leadsheets, the Sch E - K-1 matrix and region-field-line links (T-04-T17 rest; SPEC-649 AC-1.1,
AC-1.2, AC-2.3; TASK-7330, DEC-4330).

- **Leadsheets** (`GET …/leadsheets?form=`): the form's worksheets, one card a section, one line a
  `line_ref` (`1040.3b`), its amount summed in code (`leadsheet_line`, ADR-050), the fields that
  feed it, and `mismatch` when a box the field cites printed another figure (TAX-04 c: line 3b
  reads 14,280 while the 1099-DIV's box 1a reads 14,820).
- **The matrix** (`GET …/matrices/sch-e-k1`): each K-1 activity's amount lines from its worksheet,
  with the prior-year K-1's figure for the same line (the PY column). Last year's figure shows only
  to a person who may read last year's engagement too.
- **The mismatch check** (AC-1.4): a document whose cited box disagrees with its field reads
  `mismatch` in the review tree, and approving it is 409 `mismatch` with `facts.field_key`.
- **Links** (`GET …/links?evidence_version_id=`): where a field's figure sits on a document. The
  link is the field's latest version's verified `document_text` citation with its page and box
  (T-04-T14's `box_claim`), never model text (INV-2); a withdrawn, moved or shadow citation names
  nothing.

Reads only. The caller holds `return_worksheet.read` on the return's engagement; a client
principal or a wall is 404. Values are TRI: compared in code, never logged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Row, text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.api import engagement_resource_of, get_ref, work_item_engagement
from abacus.modules.evidence.api import CitationBox, citation_boxes
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.review.api import latest_citations
from abacus.modules.tax.compute.individual.forms import leadsheet_line
from abacus.modules.tax.compute.individual.k1 import sch_e_matrix
from abacus.modules.tax.form_line_citations import amount

READ: Final = "return_worksheet.read"
WORKSHEET: Final = "return_worksheet"
CENT: Final = Decimal("0.01")

LEADSHEET_FIELDS: Final = text(
    "SELECT w.id AS worksheet_id, s.key AS section_key, s.name AS section_name, f.field_key, "
    "f.line_ref, f.label, f.current_value FROM return_fields f "
    "JOIN return_worksheets w ON w.id = f.worksheet_id "
    "JOIN return_worksheet_sections s ON s.id = f.section_id "
    "WHERE f.tax_return_id = :r AND w.active AND lower(w.form_code) = lower(:form) "
    "AND f.line_ref IS NOT NULL AND f.value_type = 'amount' "
    "ORDER BY w.sort_order, w.key, s.sort_order, s.key, f.sort_order, f.field_key"
)
LINKED_FIELDS: Final = text(
    "SELECT w.id AS worksheet_id, w.form_code, f.field_key, f.line_ref, f.current_value "
    "FROM return_fields f "
    "JOIN return_worksheets w ON w.id = f.worksheet_id "
    "WHERE f.tax_return_id = :r AND w.active "
    "ORDER BY w.sort_order, w.key, f.sort_order, f.field_key"
)
RETURN_YEAR: Final = text("SELECT tax_year FROM tax_returns WHERE work_item_id = :r")
ACTIVITIES: Final = text(
    "SELECT a.id, a.k1_state, ("
    "  SELECT w.id FROM return_worksheets w WHERE w.active "
    "  AND (w.id = a.k1_worksheet_id OR w.k1_activity_id = a.id) "
    "  ORDER BY (w.id = a.k1_worksheet_id) DESC, w.sort_order, w.key LIMIT 1"
    ") AS worksheet_id FROM k1_activities a WHERE a.tax_return_id = :r "
    "ORDER BY a.issuer_name, a.id"
)
# The prior-year K-1 of the same issuer on the same client's same form (the SALY join).
PRIOR_SHEET: Final = text(
    "SELECT pa.engagement_id, ("
    "  SELECT w.id FROM return_worksheets w WHERE w.active "
    "  AND (w.id = pa.k1_worksheet_id OR w.k1_activity_id = pa.id) "
    "  ORDER BY (w.id = pa.k1_worksheet_id) DESC, w.sort_order, w.key LIMIT 1"
    ") AS worksheet_id FROM k1_activities ca "
    "JOIN tax_returns cr ON cr.work_item_id = ca.tax_return_id "
    "JOIN tax_returns pr ON pr.client_entity_id = cr.client_entity_id AND pr.form = cr.form "
    "AND pr.tax_year = cr.tax_year - 1 "
    "JOIN k1_activities pa ON pa.tax_return_id = pr.work_item_id "
    "AND pa.issuer_name = ca.issuer_name "
    "WHERE ca.id = :a ORDER BY pa.id LIMIT 1"
)
SHEET_AMOUNTS: Final = text(
    "SELECT f.field_key, f.label, f.current_value FROM return_fields f "
    "JOIN return_worksheet_sections s ON s.id = f.section_id "
    "WHERE f.worksheet_id = :w AND f.value_type = 'amount' "
    "ORDER BY s.sort_order, s.key, f.sort_order, f.field_key"
)


@dataclass(frozen=True)
class LeadLine:
    line_key: str
    label: str
    amount: Decimal | None
    contributing_field_keys: tuple[str, ...]
    mismatch: bool


@dataclass(frozen=True)
class LeadCard:
    form: str
    title: str
    lines: tuple[LeadLine, ...]


@dataclass(frozen=True)
class MatrixRow:
    activity_id: UUID
    label: str
    current_year: Decimal | None
    prior_year: Decimal | None
    status: str


@dataclass(frozen=True)
class Matrix:
    rows: tuple[MatrixRow, ...]
    tax_year: int
    prior_year: int


@dataclass(frozen=True)
class FieldLink:
    match_id: str
    evidence_version_id: UUID
    page: int
    bbox: tuple[float, float, float, float]
    field_key: str
    line_key: str | None


async def _engagement(ctx: AuthContext, return_id: UUID) -> UUID:
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None or ctx.client:
        raise NotFound("tax_return")  # INV-4: no portal principal reads a worksheet
    ref = await get_ref(ctx, engagement)  # a wall answers 404
    await authorise(ctx, READ, ref.resource())
    return engagement


def money(value: object) -> Decimal | None:
    """A field's typed value (`{t: "amount" | "decimal", v: "14820"}`) to the cent; else None."""
    if not isinstance(value, Mapping):
        return None
    raw = cast(Mapping[str, object], value).get("v")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw)).quantize(CENT)
    except InvalidOperation:
        return None


def box_disagrees(held: Decimal | None, boxes: Sequence[CitationBox]) -> bool:
    """Whether a cited box printed a figure other than the field's (code, never a model)."""
    if held is None:
        return False
    for box in boxes:
        printed = None if box.value_text is None else amount(box.value_text)
        if printed is not None and printed.quantize(CENT) != held:
            return True
    return False


async def _boxes_by_field(
    ctx: AuthContext, engagement_id: UUID, worksheet_ids: Sequence[UUID]
) -> dict[tuple[UUID, str], list[CitationBox]]:
    cited = await latest_citations(ctx.tenant, WORKSHEET, list(dict.fromkeys(worksheet_ids)))
    wanted = sorted({c for ids in cited.values() for c in ids}, key=str)
    found = {b.citation_id: b for b in await citation_boxes(ctx.tenant, engagement_id, wanted)}
    return {key: [found[c] for c in ids if c in found] for key, ids in cited.items() if ids}


def _cards(
    form: str,
    rows: Sequence[Row[Any]],  # Any: SQL rows
    boxes: Mapping[tuple[UUID, str], Sequence[CitationBox]],
) -> list[LeadCard]:
    cards: dict[tuple[UUID, str], tuple[str, dict[str, list[Row[Any]]]]] = {}  # Any: SQL rows
    for r in rows:
        _title, lines = cards.setdefault((r.worksheet_id, r.section_key), (r.section_name, {}))
        lines.setdefault(str(r.line_ref), []).append(r)
    out: list[LeadCard] = []
    code = form.lower()
    for (_sheet, _section), (title, lines) in cards.items():
        built: list[LeadLine] = []
        for line_ref, parts in lines.items():
            values = [money(p.current_value) for p in parts]
            known = [v for v in values if v is not None]
            total = leadsheet_line(line_ref, known).total if known else None
            mismatch = any(
                box_disagrees(v, boxes.get((p.worksheet_id, str(p.field_key)), ()))
                for p, v in zip(parts, values, strict=True)
            )
            built.append(
                LeadLine(
                    f"{code}.{line_ref}",
                    str(parts[0].label),
                    total,
                    tuple(str(p.field_key) for p in parts),
                    mismatch,
                )
            )
        out.append(LeadCard(form, str(title), tuple(built)))
    return out


async def leadsheets(ctx: AuthContext, return_id: UUID, form: str) -> list[LeadCard]:
    engagement = await _engagement(ctx, return_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(LEADSHEET_FIELDS, {"r": return_id, "form": form})).all()
    boxes = await _boxes_by_field(ctx, engagement, [r.worksheet_id for r in rows])
    return _cards(form, rows, boxes)


async def field_links(
    ctx: AuthContext, return_id: UUID, evidence_version_id: UUID | None
) -> list[FieldLink]:
    engagement = await _engagement(ctx, return_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(LINKED_FIELDS, {"r": return_id})).all()
    boxes = await _boxes_by_field(ctx, engagement, [r.worksheet_id for r in rows])
    out: list[FieldLink] = []
    seen: set[tuple[str, str]] = set()
    for r in rows:
        line_key = f"{str(r.form_code).lower()}.{r.line_ref}" if r.line_ref else None
        for box in boxes.get((r.worksheet_id, str(r.field_key)), ()):
            if evidence_version_id is not None and box.evidence_version_id != evidence_version_id:
                continue
            if (box.match_id, str(r.field_key)) in seen:
                continue
            seen.add((box.match_id, str(r.field_key)))
            out.append(
                FieldLink(
                    box.match_id,
                    box.evidence_version_id,
                    box.page,
                    box.bbox,
                    str(r.field_key),
                    line_key,
                )
            )
    return out


async def mismatched_documents(
    ctx: AuthContext, engagement_id: UUID, return_id: UUID
) -> dict[UUID, str]:
    """SPEC-649 AC-1.4 (the code mismatch check): each document version a box of which printed a
    figure other than the field citing it, with the first such field's key (sheet and field
    order). Identifiers only leave here. The caller has authorised a read of the return."""
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(LINKED_FIELDS, {"r": return_id})).all()
    boxes = await _boxes_by_field(ctx, engagement_id, [r.worksheet_id for r in rows])
    found: dict[UUID, str] = {}
    for r in rows:
        held = money(r.current_value)
        for box in boxes.get((r.worksheet_id, str(r.field_key)), ()):
            if box.evidence_version_id not in found and box_disagrees(held, [box]):
                found[box.evidence_version_id] = str(r.field_key)
    return found


async def _may_read(ctx: AuthContext, engagement_id: UUID) -> bool:
    try:
        await authorise(ctx, READ, await engagement_resource_of(ctx.tenant, engagement_id))
    except (Forbidden, NotFound):
        return False
    return True


async def _amounts(
    worksheet_id: UUID | None, ctx: AuthContext
) -> list[tuple[str, str, Any]]:  # Any: a field's JSON value
    if worksheet_id is None:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(SHEET_AMOUNTS, {"w": worksheet_id})).all()
    return [(str(r.field_key), str(r.label), r.current_value) for r in rows]


async def k1_matrix(ctx: AuthContext, return_id: UUID) -> Matrix:
    await _engagement(ctx, return_id)
    async with tenant_session(ctx.tenant) as session:
        year = await session.scalar(RETURN_YEAR, {"r": return_id})
        activities = (await session.execute(ACTIVITIES, {"r": return_id})).all()
    if year is None:
        raise NotFound("tax_return")
    tax_year = int(cast(int, year))
    rows: list[MatrixRow] = []
    for a in activities:
        current = [(k, label, money(v)) for k, label, v in await _amounts(a.worksheet_id, ctx)]
        async with tenant_session(ctx.tenant) as session:
            last = (await session.execute(PRIOR_SHEET, {"a": a.id})).first()
        prior: list[tuple[str, Decimal | None]] = []
        if last is not None and await _may_read(ctx, last.engagement_id):
            prior = [(k, money(v)) for k, _l, v in await _amounts(last.worksheet_id, ctx)]
        for line in sch_e_matrix(current, prior).lines:
            rows.append(
                MatrixRow(a.id, line.label, line.current_year, line.prior_year, str(a.k1_state))
            )
    return Matrix(tuple(rows), tax_year, tax_year - 1)
