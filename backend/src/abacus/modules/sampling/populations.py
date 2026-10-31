"""Populations and completeness ties (A-03-T07; A-03 §3 F2 US-2.1 to US-2.3; SPEC-580; ADR-340,
ADR-050, ADR-031, ADR-052; DEC-1660).

A population is what a sample is drawn from, frozen when it is built: its records (display fields
only), their canonical SHA-256 and their total. It comes from one of two sources.

- **Upload** (US-2.1): an evidence version on the engagement, read through `evidence.api` (which
  authorises `evidence.read` and audits the read), parsed in an isolated child process (cached
  values only; formulas never evaluated, macros never run). The column map names the record key
  (required), name, date and amount by header text or column letter. A column whose header the
  evidence masking reads as PII, or whose values it would mask, is Restricted and refused with
  422 `restricted_column` (it is never copied). Cells are kept as text, so a value starting with
  `=`, `+`, `-` or `@` is stored verbatim and neutralised only where it is exported.
- **General ledger** (US-2.3): `gl_entries` of a snapshot of the engagement's entity, read through
  `ledger.api` (never a connector write, ADR-040): the lines on the named accounts, on one side,
  of the named kinds, posted in the window. Each line is a record; its amount is that side.

Ties (US-2.2) are computed by code: the population's total minus the sum of the comparisons is
`tie` (zero) or `off` (anything else); with no total to compare it is `check`. A comparison's
citation must be verified and live on the engagement (`evidence.api.supported_citations`, INV-2)
or the tie is refused (422 `citation_unverified`). A general-ledger population gets its two
designed ties when it is built: the population against every credit (or debit) to its accounts in
the window, and the check numbers among its references without gaps (`check` with the reason in
words where the export carries none, or where numbers are missing).
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
from typing import Any, Final, Literal, cast
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.evidence.api import (
    column_families,
    extract_isolated,
    masked_rows,
    read_version,
    supported_citations,
    version_view,
)
from abacus.modules.identity.api import AuthContext, authorise, names_of
from abacus.modules.ledger.api import GlEntry, gl_entries, gl_snapshot_view
from abacus.modules.sampling import population_repository as repo
from abacus.modules.sampling.compute import Record, canonical
from abacus.modules.sampling.contract import (
    CitationOut,
    CompletenessTieOut,
    GeneralLedgerSourceIn,
    PopulationIn,
    PopulationOut,
    PopulationQueryOut,
    PopulationSourceOut,
    TieComparisonOut,
    TieIn,
    UploadSourceIn,
)

TIE_VERSION: Final = "tie-1"
COLUMN_FIELDS: Final = ("record_key", "name", "date", "amount")
GL_BATCH: Final = 5000
_LETTERS: Final = re.compile(r"^[A-Za-z]{1,3}$")
_CHECK_NUMBER: Final = re.compile(r"^\d{1,12}$")
_MONEY_NOISE: Final = re.compile(r"[\s$,]")
Result = Literal["tie", "off", "check"]
Row = Mapping[str, Any]  # Any: database rows and stored JSON of mixed column types


class RestrictedColumn(DomainInvalid):
    """A mapped column is Restricted (SSN, ITIN, DOB, bank account or routing number): never
    copied (ADR-031)."""

    code = "restricted_column"


class ColumnMapInvalid(DomainInvalid):
    """The column map names an unknown field, no record key, a column the sheet does not have,
    one column twice, or an amount column holding something other than an amount."""

    code = "column_map_invalid"


class PopulationUnreadable(DomainInvalid):
    """The evidence version could not be read as a sheet, or yields no records."""

    code = "population_unreadable"


class DuplicateRecordKey(DomainInvalid):
    """Two records' keys normalise alike: a population's key is unique (ADR-340 §2)."""

    code = "duplicate_record_key"


class CitationUnverified(DomainInvalid):
    """A comparison cites something not verified and live on the engagement (INV-2)."""

    code = "citation_unverified"


# ---- pure: parsing, records and tie arithmetic --------------------------------------------------


@dataclass(frozen=True)
class Built:
    """A population's records in canonical order, with what each displays."""

    records: tuple[Record, ...]
    display: Mapping[str, Mapping[str, str]]
    total: Decimal | None
    sha256: str


@dataclass(frozen=True)
class Tie:
    label: str
    left_amount: Decimal | None
    comparisons: tuple[Mapping[str, object], ...]
    difference: Decimal | None
    result: Result
    explanation: str | None = None
    inputs: Mapping[str, object] = field(default_factory=dict[str, object])


def _letter_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def resolve_columns(header: Sequence[str], column_map: Mapping[str, str]) -> dict[str, int]:
    """Each field's column: a header's text (case and spacing ignored) or a column letter."""
    unknown = sorted(set(column_map) - set(COLUMN_FIELDS))
    if unknown or "record_key" not in column_map:
        raise ColumnMapInvalid(facts={"field": unknown[0] if unknown else "record_key"})
    names = {" ".join(h.split()).casefold(): i for i, h in enumerate(header) if h.strip()}
    resolved: dict[str, int] = {}
    for name, wanted in column_map.items():
        key = " ".join(wanted.split()).casefold()
        if key in names:
            index = names[key]
        elif _LETTERS.fullmatch(wanted.strip()) and _letter_index(wanted.strip()) < len(header):
            index = _letter_index(wanted.strip())
        else:
            raise ColumnMapInvalid(facts={"field": name})
        if index in resolved.values():
            raise ColumnMapInvalid(facts={"field": name})
        resolved[name] = index
    return resolved


def _cell(row: Sequence[str], index: int) -> str:
    return row[index] if index < len(row) else ""


def refuse_restricted(
    header: Sequence[str], rows: Sequence[Sequence[str]], at: Mapping[str, int]
) -> None:
    """422 `restricted_column` for a mapped column the masking reads as PII, by its header or by
    any of its values (the evidence pipeline's own rules, ADR-031)."""
    for name, index in at.items():
        if column_families(_cell(header, index)):
            raise RestrictedColumn(facts={"field": name})
        column = [[_cell(header, index)], *([_cell(r, index)] for r in rows)]
        if any(m != tuple(c) for m, c in zip(masked_rows(column), column, strict=True)):
            raise RestrictedColumn(facts={"field": name})


def parse_money(text: str) -> Decimal | None:
    """An amount cell: signs, `$`, thousands separators and parentheses; blank is None."""
    raw = _MONEY_NOISE.sub("", text)
    if not raw:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    core = raw[1:-1] if negative else raw
    try:
        value = Decimal(core)
    except InvalidOperation:
        raise ColumnMapInvalid(facts={"field": "amount"}) from None
    if not value.is_finite():
        raise ColumnMapInvalid(facts={"field": "amount"})
    return -value if negative else value


def upload_records(rows: Sequence[Sequence[str]], column_map: Mapping[str, str]) -> Built:
    """US-2.1: the sheet's rows (the first non-blank row is the header) as records."""
    body = [list(r) for r in rows]
    while body and not any(c.strip() for c in body[0]):
        body.pop(0)
    if not body:
        raise PopulationUnreadable(facts={"reason": "empty"})
    header, data = body[0], body[1:]
    at = resolve_columns(header, column_map)
    refuse_restricted(header, data, at)
    records: list[Record] = []
    display: dict[str, dict[str, str]] = {}
    for row in data:
        key = _cell(row, at["record_key"]).strip()
        if not key:
            continue  # a blank line or a note under the table
        amount = parse_money(_cell(row, at["amount"])) if "amount" in at else None
        records.append(Record(key, amount))
        display[key] = {f: _cell(row, at[f]) for f in ("name", "date") if f in at}
    return _built(records, display)


def _built(records: list[Record], display: Mapping[str, Mapping[str, str]]) -> Built:
    if not records:
        raise PopulationUnreadable(facts={"reason": "no_records"})
    try:
        population = canonical(records)
    except ValueError as exc:
        if "alike" in str(exc) or "normalise" in str(exc):
            raise DuplicateRecordKey from None
        raise ColumnMapInvalid(facts={"field": "amount"}) from None
    return Built(population.records, display, population.total, population.population_hash)


@dataclass(frozen=True)
class GlQuery:
    account_codes: tuple[str, ...]
    side: Literal["debit", "credit"]
    kinds: tuple[str, ...]
    posted_from: date
    posted_to: date

    def on_side(self, e: GlEntry) -> Decimal:
        return e.credit if self.side == "credit" else e.debit

    def in_window(self, e: GlEntry) -> bool:
        return (
            e.account_code in self.account_codes
            and self.posted_from <= e.posted_on <= self.posted_to
            and self.on_side(e) > 0
        )

    def matches(self, e: GlEntry) -> bool:
        wanted = {k.casefold() for k in self.kinds}
        return self.in_window(e) and (not wanted or (e.kind or "").casefold() in wanted)


def gl_records(entries: Sequence[GlEntry], query: GlQuery) -> Built:
    """US-2.3: each matching line is a record keyed by its line, its amount the query's side."""
    records: list[Record] = []
    display: dict[str, dict[str, str]] = {}
    for e in entries:
        if not query.matches(e):
            continue
        key = f"L{e.line_no:07d}"
        records.append(Record(key, query.on_side(e)))
        display[key] = {
            "date": e.posted_on.isoformat(),
            "reference": e.reference or "",
            "counterparty": e.counterparty or "",
            "kind": e.kind or "",
        }
    return _built(records, display)


def compute_tie(
    label: str,
    left: Decimal | None,
    comparisons: Sequence[Mapping[str, object]],
    explanation: str | None = None,
) -> Tie:
    """US-2.2: `tie` when the total less the comparisons is zero, `off` otherwise, `check` with
    no total to compare. Code only (ADR-050)."""
    amounts = [Decimal(str(c["amount"])) for c in comparisons]
    if left is None or not amounts:
        return Tie(label, left, tuple(comparisons), None, "check", explanation)
    difference = left - sum(amounts, Decimal(0))
    result: Result = "tie" if difference == 0 else "off"
    return Tie(label, left, tuple(comparisons), difference, result, explanation)


def gl_ties(entries: Sequence[GlEntry], query: GlQuery, built: Built) -> list[Tie]:
    """US-2.3's two designed ties, by code."""
    side = sum((query.on_side(e) for e in entries if query.in_window(e)), Decimal(0))
    accounts = ", ".join(query.account_codes)
    window = f"{query.posted_from.isoformat()} to {query.posted_to.isoformat()}"
    whole: dict[str, object] = {
        "label": f"All {query.side}s to {accounts}, {window}",
        "amount": str(side),
        "citation_id": None,
        "ledger_ref": f"{accounts} {window}",
    }
    first = compute_tie(f"Population = {query.side}s to {accounts}", built.total, [whole])
    numbers = sorted(
        {
            int(d["reference"])
            for d in built.display.values()
            if _CHECK_NUMBER.fullmatch(d.get("reference", ""))
        }
    )
    label = "No gaps in check numbers"
    if not numbers:
        second = Tie(label, None, (), None, "check", "Check numbers not in this export")
    else:
        missing = numbers[-1] - numbers[0] + 1 - len(numbers)
        second = (
            Tie(label, None, (), None, "tie")
            if missing == 0
            else Tie(label, None, (), None, "check", f"{missing} check numbers missing")
        )
    return [first, second]


def inputs_hash(sha256: str, tie: Tie) -> str:
    document = {
        "engine_version": TIE_VERSION,
        "population": sha256,
        "label": tie.label,
        "left": None if tie.left_amount is None else str(tie.left_amount),
        "comparisons": [
            [c.get("label"), str(c.get("amount")), c.get("citation_id"), c.get("ledger_ref")]
            for c in tie.comparisons
        ],
        "explanation": tie.explanation,
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


# ---- the service


async def _gl_lines(ctx: AuthContext, snapshot_id: UUID) -> list[GlEntry]:
    lines: list[GlEntry] = []
    after = 0
    while True:
        page = await gl_entries(ctx.tenant, snapshot_id, after=after, limit=GL_BATCH)
        lines.extend(page)
        if len(page) < GL_BATCH:
            return lines
        after = page[-1].line_no


async def _upload(ctx: AuthContext, engagement_id: UUID, src: UploadSourceIn) -> Built:
    view = await version_view(ctx.tenant, src.evidence_version_id)
    if view.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    content = await read_version(ctx, src.evidence_version_id)
    extraction = await asyncio.to_thread(extract_isolated, content, view.media_type)
    if extraction.status != "extracted" or not extraction.tables:
        raise PopulationUnreadable(facts={"reason": extraction.reason or "not_a_sheet"})
    table = next((t for t in extraction.tables if t.rows), extraction.tables[0])
    return upload_records(table.rows, src.column_map)


def _query(src: GeneralLedgerSourceIn) -> GlQuery:
    return GlQuery(
        tuple(src.account_codes), src.side, tuple(src.kinds), src.posted_from, src.posted_to
    )


def record_unit(sampling_unit: str) -> str:
    """What an upload's records are called: the sampling unit's first word, plural
    ("participant (census record)" -> "participants")."""
    word = sampling_unit.split()[0].strip("(),").casefold() if sampling_unit.split() else ""
    if not word.isalpha():
        return "records"
    return word if word.endswith("s") else f"{word}s"


def _tie_row(
    ctx: AuthContext, population_id: UUID, position: int, sha: str, tie: Tie
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "tenant_id": ctx.tenant_id,
        "population_id": population_id,
        "position": position,
        "label": tie.label,
        "left_amount": tie.left_amount,
        "comparisons": json.dumps(list(tie.comparisons), default=str),
        "difference": tie.difference,
        "result": tie.result,
        "explanation": tie.explanation,
        "engine_version": TIE_VERSION,
        "inputs_hash": inputs_hash(sha, tie),
        "created_by": ctx.user_id,
    }


async def create_population(
    ctx: AuthContext, work_item_id: UUID, body: PopulationIn
) -> PopulationOut:
    """US-2.1 / US-2.3: build, store and audit a population (the route authorised the work item's
    engagement for `population.create`)."""
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work item")
    ref = await get_ref(ctx, engagement_id)
    src = body.source
    ties: list[Tie] = []
    pulled_at: datetime | None = None
    upload = src if isinstance(src, UploadSourceIn) else None
    ledger = src if isinstance(src, GeneralLedgerSourceIn) else None
    if upload is not None:
        built = await _upload(ctx, engagement_id, upload)
        unit = record_unit(body.sampling_unit)
    else:
        src = cast(GeneralLedgerSourceIn, src)
        snapshot = await gl_snapshot_view(ctx.tenant, src.gl_snapshot_id)
        if snapshot.client_entity_id != ref.client_entity_id:
            raise NotFound("gl_snapshot")
        lines = await _gl_lines(ctx, src.gl_snapshot_id)
        query = _query(src)
        built = gl_records(lines, query)
        ties = gl_ties(lines, query, built)
        unit = "payments" if src.side == "credit" else "entries"
        pulled_at = snapshot.created_at
    population_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await repo.insert_population(
            tx.session,
            {
                "id": population_id,
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "work_item_id": work_item_id,
                "source_kind": src.kind,
                "evidence_version_id": None if upload is None else upload.evidence_version_id,
                "gl_snapshot_id": None if ledger is None else ledger.gl_snapshot_id,
                "query": None
                if ledger is None
                else json.dumps(
                    ledger.model_dump(mode="json", exclude={"kind", "gl_snapshot_id"})
                ),
                "column_map": json.dumps({} if upload is None else upload.column_map),
                "record_count": len(built.records),
                "record_unit": unit,
                "amount_total": built.total,
                "sha256": built.sha256,
                "sampling_unit": body.sampling_unit,
                "deviation_definition": body.deviation_definition,
                "pulled_at": pulled_at,
                "created_by": ctx.user_id,
            },
        )
        await repo.insert_records(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "population_id": population_id,
                    "ordinal": n,
                    "record_key": r.key,
                    "amount": r.amount,
                    "display": json.dumps(dict(built.display.get(r.key, {}))),
                }
                for n, r in enumerate(built.records)
            ],
        )
        tx.record(
            "population.created",
            target=Target("population", population_id),
            after=Ref(engagement=engagement_id, records=len(built.records), sha256=built.sha256),
        )
        for position, tie in enumerate(ties, start=1):
            row = _tie_row(ctx, population_id, position, built.sha256, tie)
            await repo.insert_tie(tx.session, row)
            tx.record(
                "population.tie_recorded",
                target=Target("population", population_id),
                after=Ref(tie=cast(UUID, row["id"]), position=position),
            )
    return await population_view(ctx, population_id)


async def _population(ctx: AuthContext, population_id: UUID, action: str) -> tuple[Row, UUID]:
    async with tenant_session(ctx.tenant) as session:
        found = await repo.population(session, population_id)
    if found is None:
        raise NotFound("population")
    engagement_id = cast(UUID, found["engagement_id"])
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    return found, engagement_id


async def record_tie(ctx: AuthContext, population_id: UUID, body: TieIn) -> CompletenessTieOut:
    """US-2.2: a person's tie, computed by code; every citation verified first (INV-2)."""
    found, engagement_id = await _population(ctx, population_id, "population.create")
    cited = [c.citation_id for c in body.comparisons if c.citation_id is not None]
    if cited:
        supported = await supported_citations(ctx.tenant, engagement_id, cited)
        if any(c not in supported for c in cited):
            raise CitationUnverified
    comparisons = [
        {
            "label": c.label,
            "amount": str(c.amount),
            "citation_id": None if c.citation_id is None else str(c.citation_id),
            "ledger_ref": c.ledger_ref,
        }
        for c in body.comparisons
    ]
    total = found["amount_total"]
    tie = compute_tie(
        body.label,
        total if isinstance(total, Decimal) else None,
        comparisons,
        body.explanation,
    )
    sha = str(found["sha256"])
    async with uow(ctx.tenant) as tx:
        await repo.lock_population(tx.session, population_id)
        position = await repo.next_position(tx.session, population_id)
        row = _tie_row(ctx, population_id, position, sha, tie)
        await repo.insert_tie(tx.session, row)
        tx.record(
            "population.tie_recorded",
            target=Target("population", population_id),
            after=Ref(tie=cast(UUID, row["id"]), position=position),
        )
    return _tie_out({**row, "comparisons": comparisons})


def _tie_out(row: Row) -> CompletenessTieOut:
    raw = row["comparisons"]
    items = cast(list[Row], json.loads(raw) if isinstance(raw, str) else raw)
    return CompletenessTieOut.model_validate(
        {
            "id": row["id"],
            "position": row["position"],
            "label": row["label"],
            "left_amount": row["left_amount"],
            "comparisons": [
                TieComparisonOut(
                    label=str(c["label"]),
                    amount=Decimal(str(c["amount"])),
                    citation=None
                    if c.get("citation_id") is None
                    else CitationOut(
                        label=str(c["label"]),
                        citation_id=UUID(str(c["citation_id"])),
                        verified=True,
                    ),
                    ledger_ref=None if c.get("ledger_ref") is None else str(c["ledger_ref"]),
                )
                for c in items
            ],
            "difference": row["difference"],
            "result": row["result"],
            "explanation": row["explanation"],
            "engine_version": row["engine_version"],
            "inputs_hash": row["inputs_hash"],
        }
    )


async def population_view(ctx: AuthContext, population_id: UUID) -> PopulationOut:
    """`GET /v1/populations/{pid}`: the population, its source facts and its ties."""
    found, _ = await _population(ctx, population_id, "population.read")
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.ties(session, population_id)
    creator = cast(UUID, found["created_by"])
    names = await names_of([creator])
    query_raw = found["query"]
    query = PopulationQueryOut.model_validate(query_raw) if isinstance(query_raw, dict) else None
    source = PopulationSourceOut.model_validate(
        {
            "kind": found["source_kind"],
            "evidence_version_id": found["evidence_version_id"],
            "gl_snapshot_id": found["gl_snapshot_id"],
            "query": query,
            "pulled_at": found["pulled_at"],
        }
    )
    return PopulationOut.model_validate(
        {
            "id": found["id"],
            "engagement_id": found["engagement_id"],
            "work_item_id": found["work_item_id"],
            "source": source,
            "record_count": found["record_count"],
            "record_unit": found["record_unit"],
            "amount_total": found["amount_total"],
            "sha256": found["sha256"],
            "sampling_unit": found["sampling_unit"],
            "deviation_definition": found["deviation_definition"],
            "ties": [_tie_out(r) for r in rows],
            "created_by_name": names.get(creator, ""),
            "created_at": found["created_at"],
        }
    )
