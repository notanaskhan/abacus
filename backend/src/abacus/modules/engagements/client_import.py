"""CLI-06's bulk client import, live (P-07-T52; P-07 §3.3 Story 3.2, §4.2 M9; DEC-374, DEC-643).

- **Upload** (`client_import.run`, a live person): the file (the raw body, bounded) is parsed by
  `client_import_parse` (hostile cells inert, headings mapped) and every row scored against the
  clients the person may see: an entity holding the row's EIN (its fingerprint) is 1.0 on basis
  `ein`, else the best name candidate of the single intake's dedupe (DEC-441). A row at or above
  `AUTO_MATCH` (0.9) is set to `merge` into its match; a row with no candidate is `new`; any
  other waits for a person (`decision` null). On a firm that is not synthetic an SSN or ITIN is
  dropped, never stored, with the row note `tin_kind_not_allowed` (P-07 OQ-4); an EIN is sealed
  at parse, bound to the row. The file is kept sealed, bound to the import, for 30 days.
- **Decisions**: a person sets `new`, `merge` (into the match, or a client they name and may
  see), `keep_both` (a new client beside the match) or `skip`; 422 `import_row_invalid` for a
  decision the row can't take, 409 `import_already_run` once the import ran. Each is audited
  (`client_import.row_decided`).
- **Run** (202): claims the import (`importing`) and starts `ClientImportWorkflow`. A row still
  undecided is skipped, never merged (a merge below 0.9 is always a person's; DEC-643). Each row
  is applied in its own unit of work as the system acting for the person who ran it, with their
  walls (INV-5): `new` and `keep_both` create the client and entity (type, sealed TIN, contact),
  `merge` adds the row's contact to the client when it has an email the client lacks (a merge
  never changes a TIN on file). The row is marked applied in that unit of work, so a re-run
  applies nothing again; a row that can't be applied keeps its code (`error_code`) and the rest
  carry on. The completion writes the counts, `client_import.completed` and its outbox event.
- **Retention**: `client_import_files_erase()` empties files and sealed row TINs after 30 days.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    ColumnElement,
    FetchedValue,
    MetaData,
    Numeric,
    RowMapping,
    Table,
    and_,
    func,
    insert,
    or_,
    select,
    text,
)
from sqlalchemy import update as sql_update
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime, Integer, Text
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.client_import_parse import (
    ImportFileInvalid,
    ParsedRow,
    Source,
    parse_client_list,
)
from abacus.modules.engagements.events import ClientImportCompleted
from abacus.modules.engagements.workflows import ClientImportInput, ClientImportWorkflow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    firm_tenant_ids,
    hidden_clients,
    is_synthetic_firm,
    member_context,
    walled_from,
)
from abacus.modules.organisations.api import (
    ContactExists,
    DedupeMatch,
    EntityAttributes,
    NewContact,
    TinConflict,
    add_contact,
    add_intake_contact,
    create_client,
    dedupe_candidates,
    ein_matches,
    fingerprint_tin,
    seal_tin,
    set_entity_attributes,
)

IMPORT: Final = "client_import.run"
SUBJECT: Final = "client_import"
AUTO_MATCH: Final = 0.9  # Story 3.2: at or above, matched without a person
RETENTION: Final = timedelta(days=30)  # P-07 OQ-4: the uploaded file's own retention
_GATED_TINS: Final = frozenset({"ssn", "itin"})
_RUNNABLE: Final = "reviewing"
# What one row can meet that leaves the rest to run (its code is kept on the row).
_ROW_ERRORS: Final = (DomainConflict, DomainInvalid, DomainForbidden)
_log = get_logger(__name__)

Decision = Literal["new", "merge", "keep_both", "skip"]
# Audit refs carry integers only: a decision or source by its place here.
DECISIONS: Final[tuple[Decision, ...]] = ("new", "merge", "keep_both", "skip")
SOURCES: Final[tuple[Source, ...]] = ("cch_axcess_tax_export", "csv")

_meta = MetaData()
imports = Table(
    "client_imports",
    _meta,
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("source", Text),
    Column("file_name", Text),
    Column("file_sealed", BYTEA),
    Column("file_sha256", Text),
    Column("file_bytes", Integer),
    Column("erase_after", DateTime(timezone=True)),
    Column("erased_at", DateTime(timezone=True)),
    Column("stage", Text),
    Column("mapping", JSONB),
    Column("counts", JSONB),
    Column("started_by", PgUUID(as_uuid=True)),
    Column("started_at", DateTime(timezone=True), server_default=FetchedValue()),
    Column("run_by", PgUUID(as_uuid=True)),
    Column("run_at", DateTime(timezone=True)),
    Column("completed_at", DateTime(timezone=True)),
)
rows = Table(
    "client_import_rows",
    _meta,
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("import_id", PgUUID(as_uuid=True)),
    Column("row_no", Integer),
    Column("parsed", JSONB),
    Column("tin_sealed", BYTEA),
    Column("tin_kind", Text),
    Column("tin_last4", Text),
    Column("tin_fingerprint", BYTEA),
    Column("best_match_client_id", PgUUID(as_uuid=True)),
    Column("best_match_entity_id", PgUUID(as_uuid=True)),
    Column("score", Numeric(5, 4)),
    Column("basis", Text),
    Column("decision", Text),
    Column("merge_client_id", PgUUID(as_uuid=True)),
    Column("decided_by", PgUUID(as_uuid=True)),
    Column("decided_at", DateTime(timezone=True)),
    Column("applied_at", DateTime(timezone=True)),
    Column("result_ref", PgUUID(as_uuid=True)),
    Column("error_code", Text),
)


class ImportAlreadyRun(DomainConflict):
    """The import ran: its rows are final."""

    code = "import_already_run"


class ImportRowInvalid(DomainInvalid):
    """The row can't take this decision (a merge with nothing to merge into, a target with
    another decision, keep both without a match)."""

    code = "import_row_invalid"


class ImportFileRefused(DomainInvalid):
    """The file isn't a client list the import can read (`facts.reason`)."""

    code = "import_file_invalid"


class ImportNotRunnable(Exception):
    """The run's person is no longer a member, or the import isn't importing: nothing applies."""


@dataclass(frozen=True)
class Counts:
    rows: int
    matched: int
    to_review: int
    new: int
    skipped: int = 0
    imported: int = 0
    failed: int = 0

    def stored(self) -> dict[str, int]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass(frozen=True)
class ImportView:
    id: UUID
    source: str
    stage: str
    file_name: str
    mapping: dict[str, str]
    counts: Counts
    started_by: UUID
    started_at: datetime
    completed_at: datetime | None
    runnable: bool


@dataclass(frozen=True)
class RowView:
    id: UUID
    row_no: int
    display_name: str
    entity_type: str | None
    tin_kind: str | None
    tin_last4: str | None
    best_match_client_id: UUID | None
    best_match_name: str | None
    score: float | None
    decision: str | None
    decided_by: UUID | None
    error_code: str | None


@dataclass(frozen=True)
class RowPage:
    items: list[RowView]
    next_cursor: str | None
    total: int


# --- guards -------------------------------------------------------------------------------------


def _live_human(ctx: AuthContext) -> None:
    """Human-only (§5): never an agent, the platform, a client or support."""
    if ctx.client or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(IMPORT, "role")


async def _gate(ctx: AuthContext) -> None:
    _live_human(ctx)
    await authorise(ctx, IMPORT, Resource.firm(ctx.tenant_id))


def _file_aad(import_id: UUID) -> str:
    return f"client_import_file:{import_id}"


def _tin_aad(row_id: UUID) -> str:
    return f"client_import_row_tin:{row_id}"


# --- reads --------------------------------------------------------------------------------------

_IMPORTED = and_(
    rows.c.applied_at.is_not(None),
    rows.c.error_code.is_(None),
    rows.c.decision.in_(("new", "merge", "keep_both")),
)


def _count(condition: ColumnElement[bool]) -> ColumnElement[int]:
    return func.count().filter(condition)


async def counts_of(session: AsyncSession, import_id: UUID) -> Counts:
    """CLI-06 g's tallies, from the rows as they stand (a run's undecided rows count skipped)."""
    applied = rows.c.applied_at.is_not(None)
    found = (
        await session.execute(
            select(
                func.count(),
                _count(rows.c.decision == "merge"),
                _count(and_(rows.c.decision.is_(None), ~applied)),
                _count(rows.c.decision.in_(("new", "keep_both"))),
                _count(or_(rows.c.decision == "skip", and_(rows.c.decision.is_(None), applied))),
                _count(_IMPORTED),
                _count(and_(applied, rows.c.error_code.is_not(None), rows.c.decision != "skip")),
            ).where(rows.c.import_id == import_id)
        )
    ).one()
    return Counts(*(int(v) for v in found))


async def _import_row(session: AsyncSession, import_id: UUID) -> RowMapping:
    row = (
        (await session.execute(select(imports).where(imports.c.id == import_id)))
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound(SUBJECT)
    return row


def _view(r: RowMapping, counts: Counts) -> ImportView:
    return ImportView(
        id=cast(UUID, r["id"]),
        source=cast(str, r["source"]),
        stage=cast(str, r["stage"]),
        file_name=cast(str, r["file_name"]),
        mapping=cast(dict[str, str], r["mapping"] or {}),
        counts=counts,
        started_by=cast(UUID, r["started_by"]),
        started_at=cast(datetime, r["started_at"]),
        completed_at=cast(datetime | None, r["completed_at"]),
        runnable=r["stage"] == _RUNNABLE and r["run_at"] is None,
    )


async def get_import(ctx: AuthContext, import_id: UUID) -> ImportView:
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = await _import_row(session, import_id)
        stored = cast(dict[str, int], found["counts"] or {})
        counts = Counts(**stored) if found["completed_at"] else await counts_of(session, import_id)
    return _view(found, counts)


def _row_view(r: RowMapping, walled: frozenset[UUID] | set[UUID]) -> RowView:
    parsed = cast(dict[str, object], r["parsed"])
    match = cast(UUID | None, r["best_match_client_id"])
    shown = match is not None and match not in walled  # DEC-43: a walled match reads as none
    return RowView(
        id=cast(UUID, r["id"]),
        row_no=cast(int, r["row_no"]),
        display_name=cast(str, parsed.get("client_name", "")),
        entity_type=cast(str | None, parsed.get("entity_type")),
        tin_kind=cast(str | None, r["tin_kind"]),
        tin_last4=cast(str | None, r["tin_last4"]),
        best_match_client_id=match if shown else None,
        best_match_name=cast(str | None, parsed.get("best_match_name")) if shown else None,
        score=float(cast(float, r["score"])) if shown and r["score"] is not None else None,
        decision=cast(str | None, r["decision"]),
        decided_by=cast(UUID | None, r["decided_by"]),
        error_code=cast(str | None, r["error_code"]),
    )


def _cursor(raw: str | None) -> int:
    if raw is None:
        return 0
    if not raw.isdigit() or len(raw) > 9:
        raise DomainInvalid(facts={"field": "cursor"})
    return int(raw)


async def import_rows(
    ctx: AuthContext,
    import_id: UUID,
    *,
    cursor: str | None = None,
    limit: int | None = None,
    review: bool = False,
) -> RowPage:
    """CLI-06 g's table in file order; `review` keeps the rows waiting for a person."""
    await _gate(ctx)
    after, size = _cursor(cursor), limit or 50
    wanted = [rows.c.import_id == import_id]
    if review:
        wanted.append(and_(rows.c.decision.is_(None), rows.c.applied_at.is_(None)))
    async with tenant_session(ctx.tenant) as session:
        await _import_row(session, import_id)
        total = int((await session.execute(select(func.count()).where(*wanted))).scalar_one())
        found = (
            (
                await session.execute(
                    select(rows)
                    .where(*wanted, rows.c.row_no > after)
                    .order_by(rows.c.row_no)
                    .limit(size + 1)
                )
            )
            .mappings()
            .all()
        )
    walled = await walled_from(ctx.tenant, ctx.user_id)
    page = [_row_view(r, walled) for r in found[:size]]
    more = len(found) > size
    return RowPage(page, str(page[-1].row_no) if more and page else None, total)


# --- upload -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Scored:
    row: ParsedRow
    id: UUID
    match: DedupeMatch | None
    tin_kind: str | None
    tin_last4: str | None
    fingerprint: bytes | None
    sealed: bytes | None
    notes: tuple[str, ...]


async def _score(ctx: AuthContext, parsed: Sequence[ParsedRow], synthetic: bool) -> list[_Scored]:
    keep: dict[int, bool] = {}
    prints: dict[int, bytes] = {}
    for r in parsed:
        allowed = r.tin is not None and (synthetic or r.tin.kind not in _GATED_TINS)
        keep[r.row_no] = allowed
        if allowed and r.tin is not None and r.tin.kind == "ein":
            prints[r.row_no] = fingerprint_tin(ctx.tenant_id, r.tin.digits)
    by_ein = await ein_matches(ctx, list(prints.values()))
    scored: list[_Scored] = []
    for r in parsed:
        row_id = uuid4()
        fingerprint = prints.get(r.row_no)
        match = by_ein.get(fingerprint) if fingerprint is not None else None
        if match is None:
            candidates = await dedupe_candidates(ctx, r.client_name)
            match = candidates[0] if candidates else None
        notes = r.notes
        tin = r.tin if keep[r.row_no] else None
        if r.tin is not None and tin is None:
            notes = tuple(sorted({*notes, "tin_kind_not_allowed"}))  # OQ-4: dropped, not stored
        sealed = (
            await seal(ctx.tenant_id, tin.digits.encode(), _tin_aad(row_id))
            if tin is not None
            else None
        )
        scored.append(
            _Scored(
                r,
                row_id,
                match,
                tin.kind if tin is not None else None,
                tin.digits[-4:] if tin is not None else None,
                fingerprint if tin is not None else None,
                sealed,
                notes,
            )
        )
    return scored


def _decision(match: DedupeMatch | None) -> Decision | None:
    if match is None:
        return "new"
    return "merge" if match.score >= AUTO_MATCH else None


def _parsed(s: _Scored) -> dict[str, object]:
    r = s.row
    out: dict[str, object] = {"client_name": r.client_name, "entity_name": r.entity_name}
    for key, value in (
        ("entity_type", r.entity_type),
        ("contact_name", r.contact_name),
        ("email", r.email),
        ("best_match_name", s.match.display_name if s.match else None),
    ):
        if value is not None:
            out[key] = value
    if s.notes:
        out["notes"] = list(s.notes)
    return out


async def upload_import(
    ctx: AuthContext, source: Source, file_name: str, content: bytes
) -> ImportView:
    """Parse, score and keep the file (sealed). 422 `import_file_invalid` (`facts.reason`)."""
    await _gate(ctx)
    try:
        parsed = parse_client_list(content, source)
    except ImportFileInvalid as bad:
        raise ImportFileRefused(facts={"reason": bad.code}) from None
    synthetic = await is_synthetic_firm(ctx.tenant)
    scored = await _score(ctx, parsed.rows, synthetic)
    import_id = uuid4()
    sealed_file = await seal(ctx.tenant_id, content, _file_aad(import_id))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            insert(imports).values(
                id=import_id,
                tenant_id=ctx.tenant_id,
                source=source,
                file_name=file_name,
                file_sealed=sealed_file,
                file_sha256=hashlib.sha256(content).hexdigest(),
                file_bytes=len(content),
                stage=_RUNNABLE,
                mapping=parsed.mapping,
                counts={},
                started_by=ctx.user_id,
            )
        )
        await tx.session.execute(
            insert(rows),
            [
                {
                    "id": s.id,
                    "tenant_id": ctx.tenant_id,
                    "import_id": import_id,
                    "row_no": s.row.row_no,
                    "parsed": _parsed(s),
                    "tin_sealed": s.sealed,
                    "tin_kind": s.tin_kind,
                    "tin_last4": s.tin_last4,
                    "tin_fingerprint": s.fingerprint,
                    "best_match_client_id": s.match.client_id if s.match else None,
                    "best_match_entity_id": s.match.client_entity_id if s.match else None,
                    "score": s.match.score if s.match else None,
                    "basis": s.match.basis if s.match else None,
                    "decision": _decision(s.match),
                    "error_code": None,
                }
                for s in scored
            ],
        )
        counts = await counts_of(tx.session, import_id)
        tx.record(
            "client_import.uploaded",
            target=Target(SUBJECT, import_id),
            after=Ref(source=SOURCES.index(source), rows=counts.rows, to_review=counts.to_review),
        )
        found = await _import_row(tx.session, import_id)
    return _view(found, counts)


# --- decisions ----------------------------------------------------------------------------------


async def _merge_target(ctx: AuthContext, target: UUID) -> None:
    """A client the person may see and import into (walled or unknown: 404, DEC-43)."""
    if await hidden_clients(ctx.tenant, ctx.user_id, [target]):
        raise NotFound("client")
    try:
        await authorise(ctx, IMPORT, Resource.client(ctx.tenant_id, target))
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("client") from None
        raise


async def decide_row(
    ctx: AuthContext,
    import_id: UUID,
    row_id: UUID,
    decision: Decision,
    merge_client_id: UUID | None = None,
) -> RowView:
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = await _import_row(session, import_id)
        row = (
            (
                await session.execute(
                    select(rows).where(rows.c.id == row_id, rows.c.import_id == import_id)
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound("client_import_row")
    if found["run_at"] is not None:
        raise ImportAlreadyRun(facts={"import_id": str(import_id)})
    match = cast(UUID | None, row["best_match_client_id"])
    walled = await walled_from(ctx.tenant, ctx.user_id)
    seen = match if match is not None and match not in walled else None
    if decision != "merge" and merge_client_id is not None:
        raise ImportRowInvalid(facts={"field": "merge_client_id"})
    if decision == "keep_both" and seen is None:
        raise ImportRowInvalid(facts={"field": "decision"})
    target = (merge_client_id or seen) if decision == "merge" else None
    if decision == "merge":
        if target is None:
            raise ImportRowInvalid(facts={"field": "merge_client_id"})
        await _merge_target(ctx, target)
    async with uow(ctx.tenant) as tx:
        done = (
            (
                await tx.session.execute(
                    sql_update(rows)
                    .where(
                        rows.c.id == row_id,
                        rows.c.applied_at.is_(None),
                        rows.c.import_id.in_(
                            select(imports.c.id).where(
                                imports.c.id == import_id, imports.c.run_at.is_(None)
                            )
                        ),
                    )
                    .values(
                        decision=decision,
                        merge_client_id=target if target != match else None,
                        decided_by=ctx.user_id,
                        decided_at=func.clock_timestamp(),
                    )
                    .returning(rows)
                )
            )
            .mappings()
            .one_or_none()
        )
        if done is None:  # the run claimed the import since it was read
            raise ImportAlreadyRun(facts={"import_id": str(import_id)})
        tx.record(
            "client_import.row_decided",
            target=Target(SUBJECT, import_id),
            after=Ref(row_no=cast(int, done["row_no"]), decision=DECISIONS.index(decision)),
        )
    return _row_view(done, walled)


# --- run ----------------------------------------------------------------------------------------


def workflow_id(tenant_id: UUID, import_id: UUID) -> str:
    return f"client_import:{tenant_id}:{import_id}"


async def _dispatch(tenant_id: UUID, import_id: UUID) -> None:
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            ClientImportWorkflow,
            ClientImportInput(str(tenant_id), str(import_id)),
            id=workflow_id(tenant_id, import_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def run_import(ctx: AuthContext, import_id: UUID) -> ImportView:
    """Claim the import and start its workflow. The person who ran an import still importing
    may start it again (a dispatch that failed after the claim; the workflow id runs it once);
    anything else after the run is 409 `import_already_run`."""
    await _gate(ctx)
    async with uow(ctx.tenant) as tx:
        found = await _import_row(tx.session, import_id)
        if found["run_at"] is None and found["stage"] == _RUNNABLE:
            await tx.session.execute(
                sql_update(imports)
                .where(imports.c.id == import_id, imports.c.run_at.is_(None))
                .values(stage="importing", run_by=ctx.user_id, run_at=func.clock_timestamp())
            )
            tx.record("client_import.started", target=Target(SUBJECT, import_id))
        elif not (found["stage"] == "importing" and found["run_by"] == ctx.user_id):
            raise ImportAlreadyRun(facts={"import_id": str(import_id)})
        found = await _import_row(tx.session, import_id)
        counts = await counts_of(tx.session, import_id)
    await _dispatch(ctx.tenant_id, import_id)
    return _view(found, counts)


# --- the workflow's activities ------------------------------------------------------------------


def _system(tenant_id: UUID, import_id: UUID, person: UUID | None) -> TenantContext:
    """INV-5: the system, acting for the person who ran the import."""
    return TenantContext(
        tenant_id, "system", f"client_import:{import_id}", on_behalf_of_user_id=person
    )


class _AppliedAlready(Exception):
    """Another attempt applied the row first: this unit of work leaves nothing behind."""


async def _new_client(
    tx: UnitOfWork, person: AuthContext, row: RowMapping, parsed: dict[str, object]
) -> UUID:
    made = await create_client(
        tx,
        person.tenant_id,
        cast(str, parsed["client_name"]),
        cast(str, parsed.get("entity_name") or parsed["client_name"]),
    )
    entity_type = cast(str | None, parsed.get("entity_type"))
    if entity_type is not None:
        await set_entity_attributes(
            tx,
            made.client_entity_id,
            EntityAttributes(entity_type=entity_type),  # pyright: ignore[reportArgumentType] -- a code from ENTITY_TYPE_WORDS
        )
    sealed = cast(bytes | None, row["tin_sealed"])
    if sealed is not None:
        digits = await open_sealed(person.tenant_id, sealed, _tin_aad(cast(UUID, row["id"])))
        await seal_tin(
            tx,
            person,
            made.client_entity_id,
            digits.decode(),
            cast(Literal["ein", "ssn", "itin"], row["tin_kind"]),
            action="client_import.run",
        )
    contact = cast(str | None, parsed.get("contact_name") or parsed.get("email"))
    if contact is not None:
        await add_intake_contact(
            tx,
            person,
            client_id=made.client_id,
            entity_id=made.client_entity_id,
            name=contact,
            email=cast(str | None, parsed.get("email")),
            roles=(),
        )
    return made.client_id


async def _merge(
    tx: UnitOfWork, person: AuthContext, target: UUID, parsed: dict[str, object]
) -> UUID:
    if await hidden_clients(person.tenant, person.user_id, [target]):
        raise NotFound("client")
    email = cast(str | None, parsed.get("email"))
    if email is not None:
        name = cast(str, parsed.get("contact_name") or email)
        with suppress(ContactExists):  # the client already has it: nothing to add
            await add_contact(
                tx, person.tenant_id, target, NewContact(name, "client_person", email=email)
            )
    return target


async def _apply_row(
    tenant: TenantContext, person: AuthContext, import_id: UUID, row: RowMapping
) -> bool:
    """True when the row wrote something (a skip or an undecided row writes nothing)."""
    decision = cast(str | None, row["decision"])
    parsed = cast(dict[str, object], row["parsed"])
    async with uow(tenant) as tx:
        result: UUID | None = None
        if decision in ("new", "keep_both"):
            result = await _new_client(tx, person, row, parsed)
        elif decision == "merge":
            target = cast(UUID, row["merge_client_id"] or row["best_match_client_id"])
            result = await _merge(tx, person, target, parsed)
        claimed = (
            await tx.session.execute(
                sql_update(rows)
                .where(rows.c.id == row["id"], rows.c.applied_at.is_(None))
                .values(applied_at=func.clock_timestamp(), result_ref=result)
                .returning(rows.c.id)
            )
        ).scalar_one_or_none()
        if claimed is None:
            raise _AppliedAlready
        if result is not None:
            tx.record(
                "client_import.row_applied",
                target=Target(SUBJECT, import_id),
                after=Ref(
                    row_no=cast(int, row["row_no"]),
                    decision=DECISIONS.index(cast(Decision, decision)),
                ),
            )
        else:  # a skip, or a row nobody decided: marked applied, nothing written
            tx.record(
                "client_import.row_skipped",
                target=Target(SUBJECT, import_id),
                after=Ref(row_no=cast(int, row["row_no"])),
            )
    return result is not None


async def _fail_row(
    tenant: TenantContext, import_id: UUID, row_id: UUID, row_no: int, code: str
) -> None:
    async with uow(tenant) as tx:
        await tx.session.execute(
            sql_update(rows)
            .where(rows.c.id == row_id, rows.c.applied_at.is_(None))
            .values(applied_at=func.clock_timestamp(), error_code=code)
        )
        tx.record(
            "client_import.row_failed", target=Target(SUBJECT, import_id), after=Ref(row_no=row_no)
        )


def _error_code(exc: Exception) -> str:
    if isinstance(exc, TinConflict):
        return "tin_conflict"
    if isinstance(exc, NotFound):
        return "not_found"
    if isinstance(exc, Forbidden):
        return "forbidden"
    return cast(str, getattr(exc, "code", "invalid"))


async def apply_import(
    tenant_id: UUID, import_id: UUID, heartbeat: Callable[..., None] = lambda *_: None
) -> int:
    """Every row not yet applied, in file order; returns how many rows this attempt wrote."""
    reader = _system(tenant_id, import_id, None)
    async with tenant_session(reader) as session:
        found = await _import_row(session, import_id)
    person_id = cast(UUID | None, found["run_by"])
    if found["stage"] != "importing" or person_id is None:
        raise ImportNotRunnable
    person = await member_context(tenant_id, person_id)
    if person is None:
        raise ImportNotRunnable
    tenant = _system(tenant_id, import_id, person_id)
    async with tenant_session(reader) as session:
        pending = (
            (
                await session.execute(
                    select(rows)
                    .where(rows.c.import_id == import_id, rows.c.applied_at.is_(None))
                    .order_by(rows.c.row_no)
                )
            )
            .mappings()
            .all()
        )
    applied = 0
    for row in pending:
        heartbeat(cast(int, row["row_no"]))
        try:
            wrote = await _apply_row(tenant, person, import_id, row)
        except _AppliedAlready:
            continue
        except (*_ROW_ERRORS, NotFound, Forbidden) as exc:
            await _fail_row(
                tenant,
                import_id,
                cast(UUID, row["id"]),
                cast(int, row["row_no"]),
                _error_code(exc),
            )
            continue
        applied += int(wrote)
    return applied


async def complete_import(tenant_id: UUID, import_id: UUID, *, failed: bool = False) -> str:
    """The run's end: the counts kept on the import, the stage, the event (once)."""
    async with tenant_session(_system(tenant_id, import_id, None)) as session:
        found = await _import_row(session, import_id)
    if found["stage"] != "importing":
        return cast(str, found["stage"])
    stage = "failed" if failed else "done"
    tenant = _system(tenant_id, import_id, cast(UUID | None, found["run_by"]))
    async with uow(tenant) as tx:
        counts = await counts_of(tx.session, import_id)
        moved = (
            await tx.session.execute(
                sql_update(imports)
                .where(imports.c.id == import_id, imports.c.stage == "importing")
                .values(stage=stage, counts=counts.stored(), completed_at=func.clock_timestamp())
                .returning(imports.c.id)
            )
        ).scalar_one_or_none()
        if moved is None:
            return stage
        tx.record(
            "client_import.completed" if not failed else "client_import.failed",
            target=Target(SUBJECT, import_id),
            after=Ref(**counts.stored()),
        )
        if not failed:
            tx.emit(ClientImportCompleted(import_id=import_id))
    return stage


_DUE = text(
    "SELECT EXISTS (SELECT 1 FROM client_imports "
    "WHERE erased_at IS NULL AND erase_after <= clock_timestamp())"
)


async def erase_files() -> int:
    """One pass of the 30-day erase (a count only). Each firm in its own session, audited as the
    system there: the tables force row-level security, so `client_import_files_erase()` sees only
    the firm whose session calls it, as `anchor_chains_activity` works firm by firm."""
    total = 0
    for tenant_id in await firm_tenant_ids():
        firm = TenantContext(tenant_id, "system", "client_import:erase")
        async with tenant_session(firm) as session:
            if not await session.scalar(_DUE):
                continue
        async with uow(firm) as tx:
            count = int(
                (await tx.session.execute(text("SELECT client_import_files_erase()"))).scalar_one()
                or 0
            )
            tx.record(
                "client_import.files_erased",
                target=Target("retention", int(RETENTION.days)),
                after=Ref(count=count),
            )
        total += count
    _log.info("client_import.files_erased", count=total)
    return total
