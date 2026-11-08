"""The financial statements as a C11 document (A-06-T29; A-06 F5, F7; AUD-20; DEC-2615).

The `fs_package` kind is composed by code from one statement version, never from a firm template:
its figures are the version's linked values (code computed them, ADR-050), its notes are the
version's own rendered note templates, and nothing else may reach a client copy (AUD-20d,
INV-4). So the body holds the entity, each statement's title and period, one table per statement
and the notes, and never a citation, a source, the disclosure checklist or agent text.

- **Draft mark.** Every render here is a draft, so C11 draws the DRAFT watermark on every page
  (P-11-T07); a final render needs an approval the kind's provider confirms, and this kind's
  answers none until management's approval flows through C18 (R-02, S31).
- **AR-C 70.** A preparation engagement's statements carry "No assurance is provided." on every
  page (R-19), as C11's legend block (a legend repeats on every page).
- **Deterministic.** The same version composes the same blocks (order by position and year,
  amounts formatted here), so its sealed snapshot, content hash and bytes are the same on every
  render (DEC-44, ADR-152).

`render_statement_draft` is what send-draft calls once C10 lands: the DRAFT render, in the
caller's unit of work, a person's (`statement.send_draft`: an engagement partner or manager).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import engagement_hold_facts, engagement_label
from abacus.modules.identity.api import AuthContext

KIND: Final = "fs_package"
OWNER: Final = "statement_version"
SEND_DRAFT: Final = "statement.send_draft"
RECORD_TYPE: Final = "derived_rendering"
NO_ASSURANCE: Final = "No assurance is provided."
PREPARATION: Final = "preparation"
NOTES_HEADING: Final = "Notes to Financial Statements"
EBP_AUDIT: Final = "ebp_audit"
# The framework's captions, by the statement keys `fs_draft` writes: an entity's (US GAAP), or a
# benefit plan's (ASC 962, an `ebp_audit`). "Statements" when the paper shows two years.
_ENTITY: Final[Mapping[str, str]] = {
    "financial_position": "Financial Position",
    "activities": "Activities",
}
_PLAN: Final[Mapping[str, str]] = {
    "financial_position": "Net Assets Available for Benefits",
    "activities": "Changes in Net Assets Available for Benefits",
    "net_assets": "Net Assets Available for Benefits",
    "changes": "Changes in Net Assets Available for Benefits",
}
# Statements as of a date; the rest cover the year that ends on it.
_AS_OF: Final = frozenset({"financial_position", "net_assets"})


class UnknownStatement(DomainInvalid):
    """A statement key with no caption: refused, never guessed (DEC-2615)."""

    code = "unknown_statement"


@dataclass(frozen=True)
class Line:
    statement_key: str
    label: str
    position: int
    values: Mapping[int, Decimal]


@dataclass(frozen=True)
class Note:
    number: int
    title: str
    body: str


@dataclass(frozen=True)
class Heading:
    entity_name: str
    period_end: date
    preparation: bool
    plan: bool = False  # an employee benefit plan's statements (ASC 962)


def statement_title(statement_key: str, years: int, *, plan: bool) -> str:
    """The statement's caption, or `UnknownStatement`: never guessed (DEC-2615)."""
    caption = (_PLAN if plan else _ENTITY).get(statement_key) or _PLAN.get(statement_key)
    if caption is None or (not plan and statement_key not in _ENTITY):
        raise UnknownStatement(facts={"statement_key": statement_key})
    return f"Statement{'s' if years > 1 else ''} of {caption}"


def amount(value: Decimal) -> str:
    """Thousands separated, two places, a negative in parentheses, no currency sign."""
    text = f"{abs(value):,.2f}"
    return f"({text})" if value < 0 else text


def _long(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def period_text(statement_key: str, period_end: date, years: Sequence[int]) -> str:
    end = _long(period_end)
    prior = [y for y in years if y != period_end.year]
    if statement_key in _AS_OF:
        return f"{end} and {prior[0]}" if prior else end
    return f"Years ended {end} and {prior[0]}" if prior else f"Year ended {end}"


def _paragraph(text: str) -> dict[str, object]:
    return {"type": "paragraph", "runs": [{"type": "text", "text": text}]}


def compose_body(heading: Heading, lines: Sequence[Line], notes: Sequence[Note]) -> list[object]:
    """The document's DocBlocks, from the version's lines and notes (pure)."""
    blocks: list[object] = [{"type": "heading", "level": 1, "text": heading.entity_name}]
    if heading.preparation:
        blocks.append({"type": "legend", "text": NO_ASSURANCE})
    ordered = sorted(lines, key=lambda line: line.position)
    statements = list(dict.fromkeys(line.statement_key for line in ordered))
    for n, key in enumerate(statements):
        mine = [line for line in ordered if line.statement_key == key]
        years = sorted({y for line in mine for y in line.values}, reverse=True)
        title = statement_title(key, len(years), plan=heading.plan)
        if n > 0:
            blocks.append({"type": "page_break"})
        blocks.append({"type": "heading", "level": 2, "text": title})
        blocks.append(_paragraph(period_text(key, heading.period_end, years)))
        blocks.append(
            {
                "type": "table",
                "columns": ["", *(str(y) for y in years)],
                "rows": [
                    [
                        line.label,
                        *(amount(line.values[y]) if y in line.values else "" for y in years),
                    ]
                    for line in mine
                ],
            }
        )
    if notes:
        blocks.append({"type": "page_break"})
        blocks.append({"type": "heading", "level": 2, "text": NOTES_HEADING})
        for note in sorted(notes, key=lambda n: n.number):
            blocks.append({"type": "heading", "level": 3, "text": f"{note.number}. {note.title}"})
            blocks.extend(_paragraph(p.strip()) for p in note.body.split("\n\n") if p.strip())
    return blocks


def lines_of(rows: Sequence[Mapping[str, object]]) -> list[Line]:
    """The statements service's line rows (one per line and year) as lines with their years."""
    found: dict[object, tuple[Mapping[str, object], dict[int, Decimal]]] = {}
    for row in rows:
        _row, values = found.setdefault(row["line_id"], (row, {}))
        values[int(cast(int, row["year"]))] = Decimal(str(row["value"]))
    return [
        Line(str(r["statement_key"]), str(r["label"]), int(cast(int, r["position"])), v)
        for r, v in found.values()
    ]


async def _body(tenant: TenantContext, owner: object, _scope: object) -> Sequence[object]:
    from abacus.modules.reporting import statements
    from abacus.modules.reporting.api import OwnerRef

    if not isinstance(owner, OwnerRef) or owner.type != OWNER:
        return []
    version = await statements.version_for_render(tenant, owner.id)
    label = await engagement_label(tenant, version.engagement_id)
    if label is None or label.fiscal_period_end is None:
        raise UnknownStatement(facts={"engagement_id": str(version.engagement_id)})
    heading = Heading(
        label.client_entity_name or label.client_name,
        label.fiscal_period_end,
        label.type == PREPARATION,
        label.type == EBP_AUDIT,
    )
    notes = [
        Note(int(cast(int, n["number"])), str(n["title"]), str(n["body"])) for n in version.notes
    ]
    return compose_body(heading, lines_of(version.lines), notes)


async def _no_values(_owner: object, _scope: object) -> Mapping[str, str]:
    return {}


async def _no_approval(_ref: object) -> tuple[UUID, str] | None:
    return None  # management's approval reaches a final render through C18 (R-02, S31)


def ensure_kind() -> None:
    """Register `fs_package` with C11 once per process (and again after a test resets)."""
    from abacus.modules.reporting import api as c11

    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="financial_statements",
                variables_provider=_no_values,
                approval_provider=_no_approval,
                retention_record_type=RECORD_TYPE,
                formats=("pdf",),
                body_provider=_body,
            )
        )


async def render_statement_draft(tx: UnitOfWork, ctx: AuthContext, version_id: UUID) -> UUID:
    """The version's DRAFT render, a person's, in the caller's unit of work; answers the
    generated document's id. The caller authorised `statement.send_draft` on the version."""
    from abacus.modules.reporting import api as c11
    from abacus.modules.reporting import statements

    ensure_kind()
    version = await statements.version_for_render(ctx.tenant, version_id)
    facts = await engagement_hold_facts(ctx.tenant, version.engagement_id)
    if facts is None:
        raise UnknownStatement(facts={"engagement_id": str(version.engagement_id)})
    ticket = await c11.render(
        tx,
        c11.RenderRequest(
            kind=KIND,
            owner_ref=c11.OwnerRef(OWNER, version_id),
            scope=c11.RenderScope(
                client_id=facts.client_id,
                engagement_id=version.engagement_id,
                work_item_id=version.work_item_id,
            ),
            template_version_id=None,
            requested_by=c11.Requester("human", user_id=ctx.user_id),
            formats=("pdf",),
        ),
    )
    return ticket.generated_document_id
