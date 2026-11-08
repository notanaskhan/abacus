"""A-06-T23: AUD-17's sign-off matrix and EP-involvement read models (A-06 §4.3; AU-C 220;
SAS 146; DF-26; DEC-2238).

The matrix is every registered reviewable on the engagement by levels L1 to L5. A cell is
`signed` (initials, version and the hash prefix it was signed over), `stale` (signed over an
older hash: "Changed after sign-off"), `pending` (required, not yet signed) or `not_required`
(the owner's facts say the level is not needed). Rows sit in sections Planning, Fieldwork &
testing, Completion and Reporting: workpapers by kind (`workpapers.api.matrix_sections`), the
engagement-level reviewables (trial balance, mapping, SUM schedule, FS package) in Completion.
The footer counts by code: Prepared (L1 signed), Reviewed (L2), Partner (L4 signed of required),
EQR (L5 signed of required) and Changed after sign-off (rows with a stale cell). The L5 column is
read-only here; the EQR signs from AUD-18 (DF-26).

The EP-involvement timeline is the engagement partner's decided cards and L4 sign-offs, oldest
first: identifiers, kinds and times only, never rationale text. Callers have authorised
`sign_off.read` on the engagement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import names_of
from abacus.modules.review.api import (
    LevelState,
    decided_cards,
    reviewable_facts,
    reviewables_of,
    sign_off_states,
)
from abacus.modules.workpapers.api import matrix_sections

Section = Literal["planning", "fieldwork", "completion", "reporting"]
CellState = Literal["signed", "stale", "pending", "not_required"]
SECTIONS: Final[tuple[Section, ...]] = ("planning", "fieldwork", "completion", "reporting")
LEVELS: Final = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Cell:
    level: int
    state: CellState
    initials: str | None
    signed_by: UUID | None
    signed_at: datetime | None
    version_no: int | None
    hash_prefix: str | None


@dataclass(frozen=True)
class Row:
    target_type: str
    target_id: UUID
    code: str
    title: str
    section: Section
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Footer:
    prepared: int
    reviewed: int
    partner_signed: int
    partner_required: int
    eqr_signed: int
    eqr_required: int
    changed_after_sign_off: int


@dataclass(frozen=True)
class Matrix:
    rows: tuple[Row, ...]
    footer: Footer


@dataclass(frozen=True)
class InvolvementEntry:
    kind: Literal["decision", "sign_off"]
    at: datetime
    by_user_id: UUID
    subject: str  # a decision kind and question key, or a reviewable's code
    outcome: str  # the option key, or "L4"


def initials(name: str) -> str:
    """ "Margaret Okonkwo" -> "MO"; a one-word name keeps its first two letters."""
    parts = [p for p in name.replace("-", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def reviewed(row: Row) -> bool:
    """AUD-17's Reviewed (TASK-3398, DEC-2397, the handoff's "Reviewed 24"): prepared, and every
    review level the row requires (L2, L3) signed on its current content. A stale review isn't
    one; a row that needs neither level (the manager's review sits in L3 when the senior
    prepares; Findings and SUM need no L2 or L3) counts once prepared."""
    preparer, *reviews = row.cells[:3]
    return preparer.state == "signed" and all(
        c.state in ("signed", "not_required") for c in reviews
    )


def footer_of(rows: tuple[Row, ...]) -> Footer:
    def signed(level: int) -> int:
        return sum(1 for r in rows if r.cells[level - 1].state in ("signed", "stale"))

    def required(level: int) -> int:
        return sum(1 for r in rows if r.cells[level - 1].state != "not_required")

    return Footer(
        prepared=signed(1),
        reviewed=sum(1 for r in rows if reviewed(r)),
        partner_signed=signed(4),
        partner_required=required(4),
        eqr_signed=signed(5),
        eqr_required=required(5),
        changed_after_sign_off=sum(1 for r in rows if any(c.state == "stale" for c in r.cells)),
    )


# S28 (TASK-3400, DEC-2399): AUD-17's groups as the handoff draws them. Trial Balance and
# Materiality sit in Planning, the sample and the mapping in Fieldwork & Testing, the financial
# statements in Reporting; the rest of the engagement-level rows stay in Completion.
_SECTION_OF: Final[dict[str, Section]] = {
    "trial_balance": "planning",
    "materiality": "planning",
    "mapping_set": "fieldwork",
    "sample_set_version": "fieldwork",
    "attribute_test": "fieldwork",
    "fs_package": "reporting",
}


async def matrix(
    tenant: TenantContext, engagement_id: UUID, *, section: Section | None = None
) -> Matrix:
    reviewables = await reviewables_of(tenant, engagement_id)
    sections = await matrix_sections(tenant, engagement_id)
    facts = {
        r.target_id: await reviewable_facts(tenant, r.target_type, r.target_id)
        for r in reviewables
    }
    states: dict[UUID, list[LevelState]] = {}
    for r in reviewables:
        found = await sign_off_states(
            tenant, r.target_type, [r.target_id], {r.target_id: facts[r.target_id].content_hash}
        )
        states[r.target_id] = list(found[r.target_id])
    signers = {s.signed_by for listed in states.values() for s in listed if s.signed_by}
    names = await names_of(sorted(signers, key=str)) if signers else {}
    rows: list[Row] = []
    for r in reviewables:
        f = facts[r.target_id]
        by_level = {s.level: s for s in states[r.target_id]}
        cells: list[Cell] = []
        for level in LEVELS:
            s = by_level.get(level)
            who = s.signed_by if s is not None else None
            if s is not None and who is not None:
                cells.append(
                    Cell(
                        level,
                        "stale" if s.stale else "signed",
                        initials(names.get(who, "")),
                        who,
                        s.signed_at,
                        f.version_no,
                        f.content_hash[:8],
                    )
                )
            elif level in f.required_levels:
                cells.append(Cell(level, "pending", None, None, None, None, None))
            else:
                cells.append(Cell(level, "not_required", None, None, None, None, None))
        row_section: Section = (
            sections.get(r.target_id, "fieldwork")
            if r.target_type == "workpaper"
            else _SECTION_OF.get(r.target_type, "completion")
        )  # type: ignore[assignment] -- boto3 ships no stubs
        rows.append(Row(r.target_type, r.target_id, r.code, r.title, row_section, tuple(cells)))
    ordered = tuple(sorted(rows, key=lambda row: (SECTIONS.index(row.section), row.code)))
    shown = ordered if section is None else tuple(r for r in ordered if r.section == section)
    return Matrix(shown, footer_of(ordered))


async def ep_involvement(tenant: TenantContext, engagement_id: UUID) -> list[InvolvementEntry]:
    """The EP's decided cards and L4 sign-offs, oldest first (AU-C 220 involvement)."""
    out = [
        InvolvementEntry(
            "decision", d.decided_at, d.decided_by, f"{d.kind}:{d.question_key}", d.option_key
        )
        for d in await decided_cards(tenant, engagement_id, "engagement_partner")
    ]
    for row in (await matrix(tenant, engagement_id)).rows:
        cell = row.cells[3]
        if cell.signed_at is not None and cell.signed_by is not None:
            out.append(
                InvolvementEntry("sign_off", cell.signed_at, cell.signed_by, row.code, "L4")
            )
    return sorted(out, key=lambda e: e.at)
