"""A-05-T19: tabular source imports, code only (A-05 §4.10 F3; DEC-2068).

A census, payroll register, loan report, schedule of account balances, BrokerWindow (SDBA) detail
or trust receipts file comes in as an accepted XLSX or CSV evidence version. Evidence's isolated
extraction reads it (cached values only; formulas never evaluated, macros never run; ADR-110),
the person's column map names which header holds which field, and code does the rest:

- **Parsing**: amounts are exact decimals (`$`, thousands separators and parenthesised negatives
  read; anything else refused with the row and column, never the value); dates are ISO or
  M/D/YYYY.
- **Footing**: a register-like file foots when its rows sum to its own total row (a key cell
  reading "Total"), or to a control total the person keys from the printed report. A file that
  does not foot is refused `import_not_footing` with the difference per column; one with neither
  total is refused `import_no_control_total`.
- **Completeness ties** (census): compensation equals the PayGrid register's YTD gross (the work
  item's latest imported payroll register) and W-3 Box 1 + Box 12 D (keyed values), or the import
  is refused `import_not_tying` with each difference.
- **Sealed writes** (census): every SSN and date of birth sealed through A-05-T18's `seal_pii`;
  no plaintext ever reaches a table, a log or an audit row.

A refused import is still recorded (`status = refused`, its code and differences in `totals`), so
the import sheet shows why; nothing of its rows is written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Scope, Target, uow
from abacus.modules.assurance.ebp_participants import seal_pii, source_masked_last4
from abacus.modules.engagements.api import assurance_item
from abacus.modules.evidence.api import (
    ExtractedTable,
    extract_isolated,
    read_version,
    version_view,
)
from abacus.modules.identity.api import AuthContext, Forbidden

Kind = Literal[
    "census",
    "payroll_register",
    "loan_report",
    "account_balances",
    "sdba_detail",
    "trust_receipts",
    "hr_roster",
]
AUDIT_TARGET: Final = "ebp_source_import"
PARTICIPANT_KINDS: Final = frozenset({"census", "hr_roster"})  # rows written to ebp_participants
MAX_ROWS: Final = 20_000
ZERO: Final = Decimal("0.00")
CENT: Final = Decimal("0.01")


@dataclass(frozen=True)
class KindSpec:
    key: str
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    amounts: tuple[str, ...] = ()
    dates: frozenset[str] = frozenset()
    percents: frozenset[str] = frozenset()
    foots: bool = True  # a register foots to its total; a census ties instead


SPECS: Final[Mapping[str, KindSpec]] = {
    # A-05-T21 (DEC-2070): the HR roster, read like the census and sealed the same way, so code
    # compares SSN and date of birth on fingerprints and no model reads either.
    "hr_roster": KindSpec(
        key="participant_key",
        required=frozenset({"participant_key", "name", "hire_on"}),
        optional=frozenset({"ssn", "dob", "status", "termination_on"}),
        dates=frozenset({"dob", "hire_on", "termination_on"}),
        foots=False,
    ),
    "census": KindSpec(
        key="participant_key",
        required=frozenset({"participant_key", "name", "hire_on", "status", "compensation"}),
        optional=frozenset(
            {
                "ssn",
                "dob",
                "termination_on",
                "deferral_election_pct",
                "years_of_service",
                "vested_pct",
                "match_ytd",
            }
        ),
        amounts=("compensation", "match_ytd"),
        dates=frozenset({"dob", "hire_on", "termination_on"}),
        percents=frozenset({"deferral_election_pct", "vested_pct"}),
        foots=False,
    ),
    "payroll_register": KindSpec(
        key="pay_date",
        required=frozenset({"pay_date", "gross", "deferral"}),
        optional=frozenset({"match", "roth", "deposited_on"}),
        amounts=("gross", "deferral", "match", "roth"),
        dates=frozenset({"pay_date", "deposited_on"}),
    ),
    "loan_report": KindSpec(
        key="loan_id",
        required=frozenset({"loan_id", "participant_key", "principal_balance"}),
        optional=frozenset({"originated_on", "repayment"}),
        amounts=("principal_balance", "repayment"),
        dates=frozenset({"originated_on"}),
    ),
    "account_balances": KindSpec(
        key="account",
        required=frozenset({"account", "balance"}),
        amounts=("balance",),
    ),
    "sdba_detail": KindSpec(
        key="account",
        required=frozenset({"account", "market_value"}),
        optional=frozenset({"participant_key"}),
        amounts=("market_value",),
    ),
    "trust_receipts": KindSpec(
        key="reference",
        required=frozenset({"reference", "received_on", "amount"}),
        optional=frozenset({"rollover"}),  # A-05-T31: the waterfall's rollovers received
        amounts=("amount", "rollover"),
        dates=frozenset({"received_on"}),
    ),
}


class ImportMapInvalid(DomainInvalid):
    """The column map names a field this kind does not have, misses a required one, or names a
    header the file does not carry (facts: the field names, never cell values)."""

    code = "import_map_invalid"


class ImportUnreadable(DomainInvalid):
    code = "import_unreadable"


class ImportRefused(DomainInvalid):
    """The import was recorded as refused; `facts` carry the code and the differences."""

    code = "import_refused"


@dataclass(frozen=True)
class Refusal:
    code: str
    facts: Mapping[str, object]


@dataclass(frozen=True)
class ParsedImport:
    kind: str
    rows: tuple[Mapping[str, object], ...]
    totals: Mapping[str, Decimal]
    refusal: Refusal | None = None
    file_totals: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])


# --- parsing (pure) -----------------------------------------------------------------------------

_AMOUNT = re.compile(r"^\(?-?\$?\s*[0-9][0-9,]*(\.[0-9]+)?\)?$")
_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_TOTAL = re.compile(r"^(grand\s+)?totals?\b", re.IGNORECASE)


def amount(raw: str) -> Decimal | None:
    value = raw.strip()
    if value in ("", "-", "—"):
        return None
    if not _AMOUNT.match(value):
        raise ValueError(value)
    negative = (value.startswith("(") and value.endswith(")")) or value.startswith("-")
    digits = value.strip("()").replace("$", "").replace(",", "").replace("-", "").strip()
    try:
        parsed = Decimal(digits)
    except InvalidOperation:
        raise ValueError(value) from None
    return -parsed if negative else parsed


def day(raw: str) -> date | None:
    value = raw.strip()
    if not value:
        return None
    if m := _US_DATE.match(value):
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    try:
        return (
            datetime.fromisoformat(value).date()
            if " " in value or "T" in value
            else (date.fromisoformat(value))
        )
    except ValueError:
        raise ValueError(value) from None


def percent(raw: str) -> Decimal | None:
    value = raw.strip().removesuffix("%").strip()
    return None if not value else Decimal(value)


def ssn_digits(raw: str) -> str | None:
    """Nine digits; a numeric cell that lost its leading zeros is padded back (Excel); one the
    client's file already masks stays masked (only its last four are known)."""
    value = raw.strip()
    if not value:
        return None
    if (last4 := source_masked_last4(value)) is not None:
        return f"XXX-XX-{last4}"
    digits = "".join(c for c in value if c.isdigit())
    if value.isdigit() and len(digits) < 9:
        digits = digits.zfill(9)
    if len(digits) != 9:
        raise ValueError("ssn")
    return digits


def _cell(spec: KindSpec, name: str, raw: str) -> object:
    if name in spec.amounts:
        return amount(raw)
    if name in spec.dates:
        return day(raw)
    if name in spec.percents:
        return percent(raw)
    if name == "ssn":
        return ssn_digits(raw)
    if name == "years_of_service":
        return None if not raw.strip() else Decimal(raw.strip())
    if name == "status":
        status = raw.strip().lower()
        status = {"a": "active", "t": "terminated", "term": "terminated"}.get(status, status)
        if status not in ("active", "terminated"):
            raise ValueError(status)
        return status
    return raw.strip()


def _header(table: ExtractedTable) -> tuple[int, Sequence[str]]:
    for index, row in enumerate(table.rows):
        if any(c.strip() for c in row):
            return index, row
    raise ImportUnreadable(facts={"reason": "empty"})


def parse(
    kind: str,
    table: ExtractedTable,
    column_map: Mapping[str, str],
    control_totals: Mapping[str, Decimal] | None = None,
) -> ParsedImport:
    """The rows by the person's map, then footing; raises on a bad map, returns a refusal for a
    file that reads but does not foot or carries a bad value."""
    spec = SPECS[kind]
    allowed = spec.required | spec.optional
    unknown = sorted(set(column_map) - allowed)
    missing = sorted(spec.required - set(column_map))
    if unknown or missing:
        raise ImportMapInvalid(
            facts={"unknown": unknown[0]} if unknown else {"missing": missing[0]}
        )
    start, header = _header(table)
    positions = {h.strip().casefold(): i for i, h in enumerate(header)}
    absent = sorted(f for f, h in column_map.items() if h.strip().casefold() not in positions)
    if absent:
        raise ImportMapInvalid(facts={"header_not_found": absent[0]})
    where = {f: positions[h.strip().casefold()] for f, h in column_map.items()}
    rows: list[Mapping[str, object]] = []
    file_totals: dict[str, Decimal] = {}
    for number, raw in enumerate(table.rows[start + 1 :], start=start + 2):
        cells = {f: (raw[i] if i < len(raw) else "") for f, i in where.items()}
        if not any(v.strip() for v in cells.values()):
            continue
        if _TOTAL.match(cells[spec.key].strip()):
            try:
                file_totals = {a: amount(cells[a]) or ZERO for a in spec.amounts if a in cells}
            except ValueError:
                return _refused(kind, "import_bad_value", {"row": number, "column": spec.key})
            continue
        try:
            rows.append({f: _cell(spec, f, v) for f, v in cells.items()})
        except (ValueError, InvalidOperation):
            bad = next(f for f, v in cells.items() if not _parses(spec, f, v))
            return _refused(kind, "import_bad_value", {"row": number, "column": bad})
        if len(rows) > MAX_ROWS:
            return _refused(kind, "import_too_large", {"limit": MAX_ROWS})
    keys = [r[spec.key] for r in rows]
    if kind in PARTICIPANT_KINDS and len(set(keys)) != len(keys):
        return _refused(kind, "import_duplicate_key", {"column": spec.key})
    totals = {
        a: sum((cast(Decimal, r[a]) for r in rows if r.get(a) is not None), ZERO).quantize(CENT)
        for a in spec.amounts
        if a in column_map
    }
    parsed = ParsedImport(kind, tuple(rows), totals, file_totals=file_totals)
    if not spec.foots:
        return parsed
    printed = {**file_totals, **(control_totals or {})}
    if not printed:
        return _with_refusal(parsed, "import_no_control_total", {"columns": sorted(totals)})
    differences = {
        a: str(totals[a] - printed[a].quantize(CENT))
        for a in sorted(printed)
        if a in totals and totals[a] != printed[a].quantize(CENT)
    }
    if differences:
        return _with_refusal(parsed, "import_not_footing", {"differences": differences})
    return parsed


def _parses(spec: KindSpec, name: str, raw: str) -> bool:
    try:
        _cell(spec, name, raw)
    except (ValueError, InvalidOperation):
        return False
    return True


def _refused(kind: str, code: str, facts: Mapping[str, object]) -> ParsedImport:
    return ParsedImport(kind, (), {}, Refusal(code, facts))


def _with_refusal(parsed: ParsedImport, code: str, facts: Mapping[str, object]) -> ParsedImport:
    return ParsedImport(
        parsed.kind, parsed.rows, parsed.totals, Refusal(code, facts), parsed.file_totals
    )


def census_ties(
    compensation: Decimal,
    payroll_ytd: Decimal | None,
    w3_box1: Decimal | None,
    w3_box12d: Decimal | None,
) -> Refusal | None:
    """Census compensation = PayGrid YTD = W-3 Box 1 + Box 12 D; each tie present is checked."""
    differences: dict[str, str] = {}
    if payroll_ytd is not None and compensation != payroll_ytd.quantize(CENT):
        differences["payroll_ytd"] = str(compensation - payroll_ytd.quantize(CENT))
    if w3_box1 is not None and w3_box12d is not None:
        w3 = (w3_box1 + w3_box12d).quantize(CENT)
        if compensation != w3:
            differences["w3_box1_plus_box12d"] = str(compensation - w3)
    return Refusal("import_not_tying", {"differences": differences}) if differences else None


# --- the import (DB) ----------------------------------------------------------------------------

_INSERT_IMPORT = text(
    "INSERT INTO ebp_source_imports (tenant_id, engagement_id, work_item_id, evidence_version_id, "
    "kind, column_map, row_count, totals, sha256, status, refusal_code, imported_by) "
    "VALUES (:tenant, :engagement, :work_item, :version, :kind, CAST(:map AS jsonb), :rows, "
    "CAST(:totals AS jsonb), :sha, :status, :refusal, :user) RETURNING id, created_at"
)
_INSERT_PARTICIPANT = text(
    "INSERT INTO ebp_participants (tenant_id, engagement_id, work_item_id, import_id, "
    "participant_key, name, ssn_sealed, ssn_fp, ssn_last4, dob_sealed, dob_fp, hire_on, "
    "termination_on, status, compensation, deferral_election_pct, years_of_service, vested_pct, "
    "match_ytd) "
    "VALUES (:tenant, :engagement, :work_item, :import_id, :key, :name, :ssn_sealed, :ssn_fp, "
    ":ssn_last4, :dob_sealed, :dob_fp, :hire_on, :termination_on, :status, :compensation, "
    ":election, :years, :vested, :match_ytd)"
)
_LATEST_REGISTER = text(
    "SELECT totals FROM ebp_source_imports WHERE work_item_id = :w AND kind = 'payroll_register' "
    "AND status = 'imported' ORDER BY created_at DESC LIMIT 1"
)
_IMPORT = text(
    "SELECT id, evidence_version_id, kind, row_count, totals, status, refusal_code, created_at "
    "FROM ebp_source_imports WHERE id = :id AND work_item_id = :w"
)


@dataclass(frozen=True)
class ImportView:
    id: UUID
    evidence_version_id: UUID
    kind: str
    row_count: int | None
    totals: Mapping[str, object]
    status: str
    refusal_code: str | None
    created_at: datetime


@dataclass(frozen=True)
class Ties:
    w3_box1: Decimal | None = None
    w3_box12d: Decimal | None = None
    control_totals: Mapping[str, Decimal] = field(default_factory=dict[str, Decimal])


async def import_source(
    ctx: AuthContext,
    work_item_id: UUID,
    evidence_version_id: UUID,
    kind: Kind,
    column_map: Mapping[str, str],
    ties: Ties | None = None,
) -> ImportView:
    """A person imports a client file (the DB's actor CHECK too). Recorded either way; a refusal
    raises `ImportRefused` after its row is written."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("ebp_import.create", "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    view = await version_view(ctx.tenant, evidence_version_id)
    if view.engagement_id != item.engagement_id:
        raise NotFound("evidence_version")
    content = await read_version(ctx, evidence_version_id)
    extraction = await asyncio.to_thread(extract_isolated, content, view.media_type)
    if extraction.status != "extracted" or not extraction.tables:
        raise ImportUnreadable(facts={"reason": extraction.reason or "not_a_sheet"})
    table = next((t for t in extraction.tables if t.rows), extraction.tables[0])
    ties = ties or Ties()
    parsed = parse(kind, table, column_map, ties.control_totals)
    refusal = parsed.refusal
    if refusal is None and kind == "census":
        async with tenant_session(ctx.tenant) as session:
            register = (
                await session.execute(_LATEST_REGISTER, {"w": work_item_id})
            ).scalar_one_or_none()
        ytd = None if register is None else _decimal(cast(Mapping[str, object], register), "gross")
        refusal = census_ties(parsed.totals["compensation"], ytd, ties.w3_box1, ties.w3_box12d)
    totals: dict[str, object] = {k: str(v) for k, v in parsed.totals.items()}
    if refusal is not None:
        totals["refusal"] = dict(refusal.facts)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                _INSERT_IMPORT,
                {
                    "tenant": ctx.tenant_id,
                    "engagement": item.engagement_id,
                    "work_item": work_item_id,
                    "version": evidence_version_id,
                    "kind": kind,
                    "map": json.dumps(dict(column_map), sort_keys=True),
                    "rows": len(parsed.rows) if refusal is None else None,
                    "totals": json.dumps(totals, sort_keys=True),
                    "sha": hashlib.sha256(content).hexdigest(),
                    "status": "imported" if refusal is None else "refused",
                    "refusal": None if refusal is None else refusal.code,
                    "user": ctx.user_id,
                },
            )
        ).one()
        if refusal is None and kind in PARTICIPANT_KINDS:
            for r in parsed.rows:
                await tx.session.execute(
                    _INSERT_PARTICIPANT,
                    await _participant(ctx, item.engagement_id, work_item_id, row.id, r),
                )
        tx.record(
            "ebp_import.refused" if refusal else "ebp_import.imported",
            target=Target(AUDIT_TARGET, row.id),
            scope=Scope(engagement_id=item.engagement_id, work_item_id=work_item_id),
        )
    if refusal is not None:
        raise ImportRefused(facts={"import_id": str(row.id), **_flat(refusal)})
    return ImportView(
        row.id,
        evidence_version_id,
        kind,
        len(parsed.rows),
        totals,
        "imported",
        None,
        row.created_at,
    )


async def _participant(
    ctx: AuthContext,
    engagement_id: UUID,
    work_item_id: UUID,
    import_id: UUID,
    r: Mapping[str, object],
) -> dict[str, object]:
    key = cast(str, r["participant_key"])
    sealed = await seal_pii(
        ctx.tenant_id,
        import_id,
        key,
        cast(str | None, r.get("ssn")),
        cast(date | None, r.get("dob")),
    )
    return {
        "tenant": ctx.tenant_id,
        "engagement": engagement_id,
        "work_item": work_item_id,
        "import_id": import_id,
        "key": key,
        "name": r["name"],
        "ssn_sealed": sealed.ssn_sealed,
        "ssn_fp": sealed.ssn_fp,
        "ssn_last4": sealed.ssn_last4,
        "dob_sealed": sealed.dob_sealed,
        "dob_fp": sealed.dob_fp,
        "hire_on": r.get("hire_on"),
        "termination_on": r.get("termination_on"),
        "status": r.get("status") or "active",
        "compensation": r.get("compensation"),
        "election": r.get("deferral_election_pct"),
        "years": r.get("years_of_service"),
        "vested": r.get("vested_pct"),
        "match_ytd": r.get("match_ytd"),
    }


def _flat(refusal: Refusal) -> dict[str, str | int]:
    """The refusal as error facts (identifiers only): the reason, then the first column that
    differs and its difference unsigned, or the row and column of a bad value. Every difference,
    signed, stays on the recorded import (`totals.refusal`)."""
    flat: dict[str, str | int] = {"reason": refusal.code}
    differences = cast(Mapping[str, str], refusal.facts.get("differences", {}))
    if differences:
        column, difference = next(iter(sorted(differences.items())))
        flat |= {"column": column, "difference": difference.lstrip("-")}
    for key in ("row", "column", "limit"):
        if key in refusal.facts and key not in flat:
            flat[key] = cast(str | int, refusal.facts[key])
    return flat


def _decimal(totals: Mapping[str, object], name: str) -> Decimal | None:
    value = totals.get(name)
    return None if value is None else Decimal(str(value))


async def import_of(ctx: AuthContext, work_item_id: UUID, import_id: UUID) -> ImportView:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_IMPORT, {"id": import_id, "w": work_item_id})).first()
    if row is None:
        raise NotFound("ebp_import")
    return ImportView(
        row.id,
        row.evidence_version_id,
        row.kind,
        row.row_count,
        cast(Mapping[str, object], row.totals),
        row.status,
        row.refusal_code,
        row.created_at,
    )
