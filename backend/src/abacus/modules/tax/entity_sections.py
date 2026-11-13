"""Entity workbook sections, their sign-offs and the post-run tie-outs (T-05-T42; T-05 F7, F8;
TXP-07, TXP-10, TXP-00; ADR-050, ADR-005; DEC-4705, DEC-4706). Amber.

- **Sections** are fixed by code (`SECTIONS`: key, title and the sheets each covers). A section's
  stable id is its `tax_workbook_sections` row (0860), written the first time it is read or
  signed; it is the `tax_workbook_section` reviewable P-04 signs. Its content hash is the SHA-256
  of its sheets' current cells (canonical JSON, by code), so any edit or run that changes a cell
  makes an earlier sign-off compute stale (P-04's own rule: the hash moved).
- **Tie-outs** (`tie_outs`) are code over the workbook's cells: the TB foots (01's ATB total is
  0), every partner's capital rolls forward (05: B + C - D + E = F), Item L ties the M-2 (Σ 05 F
  = 07 B9) and Σ K-1 = K per Schedule K line (09's shares sum to 06 C). Each answers its state,
  difference, the cells it reads (`cell_range` links) and the section it belongs to.
- **Sign-off** (`POST …/sections/{key}/sign-off`): with any of the section's tie-outs off and no
  note, 409 `tie_out_off` (with the count); with a note, P-04's sign-off is recorded and the note
  is sealed beside it (`tax_section_acknowledgements`), audited `tie_out.off_acknowledged` with
  the note's hash only. Then `tax_section.signed_off`. P-04's rules decide who may sign which
  level (an agent never; the preparer never reviews).
- **After every run** (`on_run_state_changed`, a terminal `agent_run.state_changed` on a return's
  run): each off tie-out raises one `review_point` issue as the system, deduplicated on
  `tie_out:<key>` (a resolved one reopens), with links to its cells and a "Why this was
  surfaced" note composed by a fixed template from code facts (no model text); each passing
  tie-out resolves its open issue as the system.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import OutboxEvent, Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    current_values,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.tax.workbook_service import WORKBOOK

TARGET: Final = "tax_workbook_section"
ZERO: Final = Decimal(0)
Values = Mapping[str, Mapping[str, object]]
State = Literal["tie", "off", "pending"]


@dataclass(frozen=True)
class WorkbookPart:
    key: str
    title: str
    sheets: tuple[str, ...]


SECTIONS: Final[tuple[WorkbookPart, ...]] = (
    WorkbookPart("trial-balance", "Financials", ("01", "03")),
    WorkbookPart("fixed-assets", "Fixed Assets", ("02",)),
    WorkbookPart("allocation", "Allocation", ("04",)),
    WorkbookPart("capital-accounts", "Capital Accounts", ("05", "07")),
    WorkbookPart("schedule-k", "Schedule K", ("06", "09")),
    WorkbookPart("states", "States", ("08",)),
)
_BY_KEY: Final = {s.key: s for s in SECTIONS}


class TieOutOff(DomainConflict):
    """A section with an off tie-out is signed only with a note (TXP-07 b2)."""

    code = "tie_out_off"


class SectionUnknown(NotFound):
    """No such section on the entity workbook."""


# --- pure: cells, hashes and tie-outs ---


def _dec(values: Values, key: str) -> Decimal | None:
    cell = values.get(key)
    if cell is None or cell.get("v") in (None, ""):
        return None
    try:
        return Decimal(str(cell["v"]))
    except ArithmeticError:
        return None


def _text(values: Values, key: str) -> str:
    cell = values.get(key)
    return "" if cell is None or cell.get("v") is None else str(cell["v"])


def _rows(values: Values, sheet: str, col: str = "A") -> list[int]:
    out: list[int] = []
    n = 2
    while f"{sheet}!{col}{n}" in values:
        out.append(n)
        n += 1
    return out


def section_hash(section: WorkbookPart, values: Values) -> str:
    """SHA-256 of the section's sheets' cells, canonical JSON (what a sign-off covers)."""
    cells = {
        k: dict(v)
        for k, v in sorted(values.items())
        if k.partition("!")[0] in section.sheets and not k.endswith(":f")
    }
    body = json.dumps(cells, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def _fmt(amount: Decimal | None) -> str:
    return "—" if amount is None else f"{amount:,.0f}"


@dataclass(frozen=True)
class TieOut:
    key: str
    section: str
    label: str
    state: State
    difference: Decimal | None
    links: tuple[Mapping[str, str], ...] = ()
    facts: Mapping[str, str] = field(default_factory=dict[str, str])

    @property
    def why(self) -> str:
        """ "Why this was surfaced", by a fixed template from code facts (never model text)."""
        return WHY[self.key.partition(":")[0]].format(**self.facts)


WHY: Final[Mapping[str, str]] = {
    "tb_foots": "The adjusted trial balance totals {total} on 01, not 0.",
    "capital_rollforward": (
        "{count} partner rows on 05 do not roll forward: beginning + contributions - "
        "distributions + income ≠ ending."
    ),
    "item_l_m2": (
        "M-2 line 9 is {m2}; the partners' ending capital on 05 totals {item_l}; off {difference}."
    ),
    "k1_sum_k": "{count} Schedule K lines do not equal the sum of the partners' K-1 shares.",
}


def tie_outs(values: Values) -> list[TieOut]:
    """The workbook's tie-outs (module docstring), by code."""
    out: list[TieOut] = []
    tb_rows = _rows(values, "01")
    if tb_rows:
        total_row = tb_rows[-1] + 1 if f"01!F{tb_rows[-1] + 1}" in values else tb_rows[-1]
        total = _dec(values, f"01!F{total_row}") or ZERO
        out.append(
            TieOut(
                "tb_foots", "trial-balance", "Trial balance foots",
                "tie" if total == ZERO else "off", total,
                ({"sheet": "01", "range": f"F{total_row}"},), {"total": _fmt(total)},
            )
        )  # fmt: skip
    partners = [n for n in _rows(values, "05") if _text(values, f"05!A{n}")]
    if partners:
        broken: list[int] = []
        for n in partners:
            b, c, d, e, f = (_dec(values, f"05!{col}{n}") or ZERO for col in "BCDEF")
            if b + c - d + e != f:
                broken.append(n)
        out.append(
            TieOut(
                "capital_rollforward", "capital-accounts", "Capital rolls forward",
                "off" if broken else "tie", Decimal(len(broken)) if broken else ZERO,
                tuple({"sheet": "05", "range": f"B{n}:F{n}"} for n in broken),
                {"count": str(len(broken))},
            )
        )  # fmt: skip
        m2 = _dec(values, "07!B9")
        endings = sum((_dec(values, f"05!F{n}") or ZERO for n in partners), ZERO)
        if m2 is None:
            out.append(
                TieOut(
                    "item_l_m2", "capital-accounts", "Item L ties M-2", "pending", None,
                    (), {"m2": "—", "item_l": _fmt(endings), "difference": "—"},
                )
            )  # fmt: skip
        else:
            difference = endings - m2
            out.append(
                TieOut(
                    "item_l_m2", "capital-accounts", "Item L ties M-2",
                    "tie" if difference == ZERO else "off", difference,
                    (
                        {"sheet": "05", "range": f"F{partners[0]}:F{partners[-1]}"},
                        {"sheet": "07", "range": "B9"},
                    ),
                    {"m2": _fmt(m2), "item_l": _fmt(endings), "difference": _fmt(abs(difference))},
                )
            )  # fmt: skip
    lines = _rows(values, "06")
    columns: list[str] = []
    col = 0
    while f"09!{chr(ord('B') + col)}1" in values:
        columns.append(chr(ord("B") + col))
        col += 1
    if lines and columns:
        off_lines: list[int] = []
        for n in lines:
            total = _dec(values, f"06!C{n}") or ZERO
            shares = sum((_dec(values, f"09!{c}{n}") or ZERO for c in columns), ZERO)
            if shares != total:
                off_lines.append(n)
        last = columns[-1]
        out.append(
            TieOut(
                "k1_sum_k", "schedule-k", "Σ K-1 = K", "off" if off_lines else "tie",
                Decimal(len(off_lines)),
                tuple(
                    link
                    for n in off_lines
                    for link in ({"sheet": "06", "range": f"C{n}"},
                                 {"sheet": "09", "range": f"B{n}:{last}{n}"})
                ),
                {"count": str(len(off_lines))},
            )
        )  # fmt: skip
    return out


def section_tie_outs(section: WorkbookPart, values: Values) -> list[TieOut]:
    return [t for t in tie_outs(values) if t.section == section.key]


# --- sections as reviewables ---

_SECTION_ROW: Final = text(
    "SELECT id, key, engagement_id, work_item_id FROM tax_workbook_sections WHERE id = :i"
)
_SECTIONS_OF: Final = text(
    "SELECT id, key FROM tax_workbook_sections WHERE work_item_id = :r ORDER BY key"
)
_SECTIONS_OF_ENGAGEMENT: Final = text(
    "SELECT id, key, work_item_id FROM tax_workbook_sections WHERE engagement_id = :e "
    "ORDER BY work_item_id, key"
)
_ENSURE: Final = text(
    "INSERT INTO tax_workbook_sections (tenant_id, engagement_id, work_item_id, key) "
    "SELECT :t, :e, :r, k FROM unnest(CAST(:keys AS text[])) AS k "
    "ON CONFLICT (work_item_id, key) DO NOTHING"
)


async def ensure_sections(
    ctx: AuthContext, return_id: UUID, engagement_id: UUID
) -> dict[str, UUID]:
    """The return's section rows, written the first time (the caller authorised a read)."""
    async with tenant_session(ctx.tenant) as session:
        found = {
            str(r["key"]): r["id"]
            for r in (await session.execute(_SECTIONS_OF, {"r": return_id})).mappings()
        }
    missing = [s.key for s in SECTIONS if s.key not in found]
    if missing:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                _ENSURE, {"t": ctx.tenant_id, "e": engagement_id, "r": return_id, "keys": missing}
            )
            rows = (await tx.session.execute(_SECTIONS_OF, {"r": return_id})).mappings().all()
            tx.record(
                "tax_section.opened",
                target=Target(WORKBOOK, return_id),
                after=Ref(sections=len(missing)),
                scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
            )
        found = {str(r["key"]): r["id"] for r in rows}
    return found


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_SECTIONS_OF_ENGAGEMENT, {"e": engagement_id})).mappings()
        rows = list(rows)
    out: list[Reviewable] = []
    cache: dict[UUID, Values] = {}
    for r in rows:
        section = _BY_KEY.get(str(r["key"]))
        if section is None:
            continue
        values = cache.get(r["work_item_id"])
        if values is None:
            values = await current_values(tenant, WORKBOOK, r["work_item_id"])
            cache[r["work_item_id"]] = values
        out.append(
            Reviewable(
                TARGET, r["id"], f"section:{r['work_item_id']}:{section.key}", section.title,
                section_hash(section, values), True,
            )
        )  # fmt: skip
    return out


async def facts(tenant: TenantContext, section_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_SECTION_ROW, {"i": section_id})).mappings().first()
    if row is None:
        return None
    section = _BY_KEY.get(str(row["key"]))
    if section is None:
        return None
    values = await current_values(tenant, WORKBOOK, row["work_item_id"])
    cells = [k for k in values if k.partition("!")[0] in section.sheets and not k.endswith(":f")]
    return ReviewableFacts(
        target_type=TARGET,
        target_id=section_id,
        engagement_id=row["engagement_id"],
        content_hash=section_hash(section, values),
        version_no=max(1, len(cells)),
        preparer_user_ids=frozenset(),
        required_levels=(1, 2),
        label=section.title,
        context_label="Entity return",
        work_item_id=row["work_item_id"],
        cell_count=len(cells),
        requirement_key=TARGET,
    )


# --- the read and the sign-off ---


@dataclass(frozen=True)
class SectionView:
    key: str
    title: str
    section_id: UUID
    content_hash: str
    tallies: tuple[TieOut, ...]
    signed_levels: tuple[str, ...]
    stale_levels: tuple[str, ...]


async def sections_view(
    ctx: AuthContext, return_id: UUID, engagement_id: UUID
) -> list[SectionView]:
    """Every section with its tallies, its signed levels and which computed stale."""
    from abacus.modules.review.api import sign_off_states

    ids = await ensure_sections(ctx, return_id, engagement_id)
    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    hashes = {ids[s.key]: section_hash(s, values) for s in SECTIONS}
    states = await sign_off_states(ctx.tenant, TARGET, list(hashes), hashes)
    every = tie_outs(values)
    out: list[SectionView] = []
    for s in SECTIONS:
        sid = ids[s.key]
        levels = states.get(sid, [])
        out.append(
            SectionView(
                s.key, s.title, sid, hashes[sid],
                tuple(t for t in every if t.section == s.key),
                tuple(f"l{lv.level}" for lv in levels if lv.signed_by and not lv.stale),
                tuple(f"l{lv.level}" for lv in levels if lv.signed_by and lv.stale),
            )
        )  # fmt: skip
    return out


@dataclass(frozen=True)
class SignedSection:
    sign_off_id: UUID
    acknowledged_off: int


async def sign_section(
    ctx: AuthContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    key: str,
    level: int,
    seen_hash: str,
    note: str | None,
    statement_version: str | None = None,
) -> SignedSection:
    """The tie-out precheck, then P-04's sign-off (its rules: a person, the level's role, R-SO-3),
    then the sealed note when a tie-out was off."""
    from abacus.kernel.crypto import seal
    from abacus.modules.review.api import STATEMENTS, sign_target

    section = _BY_KEY.get(key)
    if section is None:
        raise SectionUnknown(key)
    ids = await ensure_sections(ctx, return_id, engagement_id)
    values = await current_values(ctx.tenant, WORKBOOK, return_id)
    off = [t for t in section_tie_outs(section, values) if t.state == "off"]
    text_note = (note or "").strip()
    if off and not text_note:
        raise TieOutOff(facts={"count": len(off)})
    signed = await sign_target(
        ctx, TARGET, ids[key], level, seen_hash,
        statement_version or STATEMENTS[level].version,
    )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        scope = Scope(engagement_id=engagement_id, work_item_id=return_id)
        if off:
            digest = hashlib.sha256(text_note.encode()).hexdigest()
            sealed = await seal(
                ctx.tenant_id, text_note.encode(),
                hashlib.sha256(f"tax_section_note:{signed.id}".encode()).hexdigest(),
            )  # fmt: skip
            await tx.session.execute(
                text(
                    "INSERT INTO tax_section_acknowledgements (tenant_id, engagement_id, "
                    "work_item_id, section_id, sign_off_id, off_count, note_sealed, note_sha256, "
                    "created_by) VALUES (:t, :e, :r, :s, :so, :n, :sealed, :sha, :by)"
                ),
                {
                    "t": ctx.tenant_id, "e": engagement_id, "r": return_id, "s": ids[key],
                    "so": signed.id, "n": len(off), "sealed": sealed, "sha": digest,
                    "by": ctx.user_id,
                },
            )  # fmt: skip
            tx.record(
                "tie_out.off_acknowledged",
                target=Target(TARGET, ids[key]),
                after=Ref(sign_off=signed.id, off=len(off), note_sha256=digest),
                scope=scope,
            )
        tx.record(
            "tax_section.signed_off",
            target=Target(TARGET, ids[key]),
            after=Ref(sign_off=signed.id, level=level),
            scope=scope,
        )
    return SignedSection(signed.id, len(off))


# --- after every run ---

RUN_DONE: Final = frozenset(
    {"succeeded", "failed", "approved", "partially_approved", "rejected", "completed"}
)


async def tie_out_check(tenant_id: UUID, return_id: UUID) -> tuple[list[UUID], list[UUID]]:
    """Raise or resolve the return's tie-out issues as the system (module docstring). Returns
    the issues raised or reopened, and those resolved."""
    from abacus.modules.engagements.api import work_item_engagement
    from abacus.modules.review.api import record_self_check_issue, system_resolve_self_checks

    system = TenantContext(tenant_id, "system", f"tie_out_check:{return_id}")
    engagement_id = await work_item_engagement(system, return_id)
    if engagement_id is None:
        return [], []
    values = await current_values(system, WORKBOOK, return_id)
    raised: list[UUID] = []
    passing: list[str] = []
    for t in tie_outs(values):
        ref = f"tie_out:{t.key}"
        if t.state == "off":
            issue, moved = await record_self_check_issue(
                system, engagement_id=engagement_id, work_item_id=return_id,
                record_type="tax_return", record_id=return_id, source_ref=ref,
                title=f"{t.label}: off {_fmt(abs(t.difference or ZERO))}",
                internal_note=t.why, links=t.links, category_path="tie_outs",
            )  # fmt: skip
            if moved:
                raised.append(issue)
        elif t.state == "tie":
            passing.append(ref)
    resolved = await system_resolve_self_checks(system, return_id, passing)
    return raised, resolved


async def on_run_state_changed(event: OutboxEvent) -> None:
    """A return's workbook run reached a terminal state: run the tie-outs (TXP-10's queue)."""
    from abacus.modules.agents.api import run_work_item_ref

    p = event.payload
    if p.get("state") not in RUN_DONE or not isinstance(p.get("run_id"), str):
        return
    ref = await run_work_item_ref(
        TenantContext(event.tenant_id, "system", "tie_out_check"), UUID(str(p["run_id"]))
    )
    if ref is None or not ref.startswith("tax_return:"):
        return
    try:
        return_id = UUID(ref.removeprefix("tax_return:"))
    except ValueError:
        return
    await tie_out_check(event.tenant_id, return_id)


def register() -> None:
    """At the tax api's import: the section reviewable and its facts."""
    register_reviewable(TARGET, reviewables)
    register_reviewable_facts(TARGET, facts)


__all__ = [
    "SECTIONS",
    "TARGET",
    "WHY",
    "SectionView",
    "SignedSection",
    "TieOut",
    "TieOutOff",
    "WorkbookPart",
    "ensure_sections",
    "on_run_state_changed",
    "register",
    "section_hash",
    "section_tie_outs",
    "sections_view",
    "sign_section",
    "tie_out_check",
    "tie_outs",
]
