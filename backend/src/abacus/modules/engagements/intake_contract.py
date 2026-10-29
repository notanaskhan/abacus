"""The intake and import contract, v1: CLI-06 single intake and bulk import (P-07-T37 stub;
ADR-139, P-36). Contract: `docs/contracts/intake-import.md`; spec: SPEC-332; DEC-374.

Live for every firm since P-07-T59 retired `clients.v2` (DEC-905). Dedupe, the intake
drafts and the commit are live (P-07-T42, `intake.py`, DEC-430); the client imports are live
(P-07-T52, `client_import.py`, DEC-643).

- **Dedupe** takes the name in the body, never the URL, and answers scored candidates.
- **Intake drafts** hold identifiers and typed values only (no TIN, no free text beyond names);
  autosaved with `seen_version`; the owner's only. **Commit** is one unit of work (client or a
  new entity of an existing client, relationships, contacts, Prospect engagements with their
  work items, the conflict check linked, and with `start_acceptance` an acceptance record) and
  requires an `Idempotency-Key`.
- **Client imports**: the file is the raw request body (SPEC-008 D3's upload, as evidence's;
  no multipart), its source and name as query parameters; rows are scored and a person decides
  each one below the auto-match threshold; **run** (202) requires an `Idempotency-Key`. A row's
  TIN is its kind and last four, and an offshore reader gets even that masked (`mask_tins_for`,
  AC9.4).

Every route refuses a client principal, an agent and the system, authorises its action
firm-level, and only then reads its flag (DEC-326's order). No model has a hidden-by-wall field
or a count of walled clients (DEC-43).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import EngagementStatus
from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements import client_import
from abacus.modules.engagements import intake as intake_model
from abacus.modules.engagements.client_import_parse import MAX_BYTES as MAX_IMPORT_BYTES
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.api import MaskedTinOut, dedupe_candidates

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

Name = Annotated[SingleLineText, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,64}$")]
ClientKind = Literal["household", "business", "plan_sponsor", "nonprofit", "trust_family"]
IntakeStep = Literal["entity", "relationships", "contacts", "services", "conflicts", "review"]
IntakeMode = Literal["new_client", "existing_client"]
ImportSource = Literal["cch_axcess_tax_export", "csv"]
ImportStage = Literal["uploaded", "mapped", "reviewing", "importing", "done", "failed"]
RowDecision = Literal["new", "merge", "keep_both", "skip"]
TinKind = Literal["ssn", "ein", "itin"]
MatchBasis = Literal["name", "ein"]


# --- dedupe -------------------------------------------------------------------------------------


class DedupeIn(BaseModel):
    """The name is in the body so it never reaches a URL or an access log."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Annotated[Name, classified("confidential")]
    kind: Annotated[ClientKind | None, classified("internal")] = None


class DedupeCandidateOut(BaseModel):
    """A client the person may see (walled clients are never candidates), with its score."""

    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    entity_name: Annotated[str | None, classified("confidential")] = None
    score: Annotated[float, Field(ge=0, le=1), classified("internal")]
    basis: Annotated[MatchBasis, classified("internal")]


class DedupeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: Annotated[list[DedupeCandidateOut], classified("confidential")] = []


# --- intake drafts and commit -------------------------------------------------------------------


class IntakeEntityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    mode: Annotated[IntakeMode, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")] = None  # existing_client
    client_display_name: Annotated[Name | None, classified("confidential")] = None  # new_client
    entity_name: Annotated[Name | None, classified("confidential")] = None
    entity_type: Annotated[Code | None, classified("internal")] = None
    date_of_death: Annotated[date | None, classified("confidential")] = None


class IntakeRelationshipIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Code, classified("internal")]  # `entity_relationships.kind`
    related_entity_id: Annotated[UUID, classified("internal")]


class IntakeContactIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    display_name: Annotated[Name, classified("confidential")]
    email: Annotated[
        str | None,
        Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+$"),
        classified("confidential"),
    ] = None
    roles: Annotated[list[Code], Field(max_length=10), classified("internal")] = []


class IntakeServiceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type_code: Annotated[Code, classified("internal")]  # an ENG-03 catalogue code, or `form_56`
    # The type's forms this service creates (P-07-T42, additive): default all of them, so
    # `forms_706_709` with `["706"]` is the estate's Form 706 alone.
    forms: Annotated[list[Code] | None, Field(max_length=5), classified("internal")] = None
    fiscal_period_start: Annotated[date | None, classified("confidential")] = None
    fiscal_period_end: Annotated[date | None, classified("confidential")] = None


class ClientIntakeDraftPayload(BaseModel):
    """Identifiers and typed values only: no TIN (entered on the entity, sealed, after commit),
    no free text beyond names (P-07 §4.2 M8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: Annotated[IntakeEntityIn | None, classified("confidential")] = None
    relationships: Annotated[
        list[IntakeRelationshipIn], Field(max_length=20), classified("internal")
    ] = []
    contacts: Annotated[
        list[IntakeContactIn], Field(max_length=20), classified("confidential")
    ] = []
    services: Annotated[list[IntakeServiceIn], Field(max_length=10), classified("internal")] = []
    engagement_partner_user_id: Annotated[UUID | None, classified("internal")] = None
    conflict_check_id: Annotated[UUID | None, classified("internal")] = None


class ClientIntakeDraftIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Annotated[IntakeStep, classified("internal")] = "entity"
    payload: Annotated[ClientIntakeDraftPayload | None, classified("confidential")] = None


class ClientIntakeDraftPatchIn(BaseModel):
    """Autosave: absent fields are unchanged; `seen_version` behind answers 409
    `stale_version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    step: Annotated[IntakeStep | None, classified("internal")] = None
    payload: Annotated[ClientIntakeDraftPayload | None, classified("confidential")] = None


class ClientIntakeDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    step: Annotated[IntakeStep, classified("internal")]
    payload: Annotated[ClientIntakeDraftPayload, classified("confidential")]
    committed_client_id: Annotated[UUID | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]
    saved_at: Annotated[datetime, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


class ClientIntakeDraftDiscardedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    discarded_at: Annotated[datetime, classified("internal")]


class IntakeValidateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Annotated[IntakeStep, classified("internal")]


class IntakeProblemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: Annotated[str, classified("internal")]  # a payload field code
    code: Annotated[str, classified("internal")]  # e.g. `required`, `date_of_death_required`


class IntakeValidationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    step: Annotated[IntakeStep, classified("internal")]
    valid: Annotated[bool, classified("internal")]
    problems: Annotated[list[IntakeProblemOut], classified("internal")] = []


class IntakeCommitIn(BaseModel):
    """ "Create & start acceptance" (`start_acceptance`) or "Create"."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_acceptance: Annotated[bool, classified("internal")] = False


class IntakeCommittedOut(BaseModel):
    """One unit of work; a replay with the same `Idempotency-Key` answers the same body."""

    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    client_entity_id: Annotated[UUID, classified("internal")]
    engagement_ids: Annotated[list[UUID], classified("internal")] = []
    engagement_status: Annotated[EngagementStatus, classified("internal")]  # `prospect`
    work_item_ids: Annotated[list[UUID], classified("internal")] = []
    conflict_check_id: Annotated[UUID | None, classified("internal")] = None
    acceptance_record_id: Annotated[UUID | None, classified("internal")] = None


# --- client imports -----------------------------------------------------------------------------


class ClientImportCountsOut(BaseModel):
    """CLI-06 g: "204 matched · 8 to review · 0 new"; after the run, imported and skipped."""

    model_config = ConfigDict(frozen=True)

    rows: Annotated[int, classified("internal")]
    matched: Annotated[int, classified("internal")]
    to_review: Annotated[int, classified("internal")]
    new: Annotated[int, classified("internal")]
    skipped: Annotated[int, classified("internal")] = 0
    imported: Annotated[int, classified("internal")] = 0
    failed: Annotated[int, classified("internal")] = 0


class ClientImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    source: Annotated[ImportSource, classified("internal")]
    stage: Annotated[ImportStage, classified("internal")]  # not a registry status (DEC-374)
    file_name: Annotated[str, classified("confidential")]
    mapping: Annotated[dict[str, str], classified("internal")] = {}  # column → field code
    counts: Annotated[ClientImportCountsOut, classified("internal")]
    started_by: Annotated[UUID, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    completed_at: Annotated[datetime | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class ClientImportRowOut(BaseModel):
    """One parsed row: cells are inert text (ADR-052); a TIN sealed at parse and shown only in
    the masked shape (kind, presence, last four)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    row_no: Annotated[int, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    entity_type: Annotated[str | None, classified("internal")] = None
    tin: Annotated[MaskedTinOut | None, classified("restricted", pii_kind="tin")] = None
    best_match_client_id: Annotated[UUID | None, classified("internal")] = None
    best_match_name: Annotated[str | None, classified("confidential")] = None
    score: Annotated[float | None, classified("internal")] = None
    decision: Annotated[RowDecision | None, classified("internal")] = None
    decided_by: Annotated[UUID | None, classified("internal")] = None
    error_code: Annotated[str | None, classified("internal")] = None


class ClientImportRowsOut(BaseModel):
    """The list envelope's shape (P-36): rows, a cursor and the total."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ClientImportRowOut], classified("confidential")] = []
    next_cursor: Annotated[str | None, classified("internal")] = None
    total: Annotated[int, classified("internal")]


class RowDecisionIn(BaseModel):
    """A person's decision on a row; `merge` names the client it merges into."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Annotated[RowDecision, classified("internal")]
    merge_client_id: Annotated[UUID | None, classified("internal")] = None


# --- routes -------------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, action: str) -> None:
    """DEC-326's order: refuse a client principal, an agent and the system, then authorise
    firm-level (`clients.v2` retired with P-07-T59, DEC-905)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


dedupe_router = AbacusRouter(prefix="/v1/clients", tags=["intake"])
client_intake_drafts_router = AbacusRouter(prefix="/v1/client-intake-drafts", tags=["intake"])
client_imports_router = AbacusRouter(prefix="/v1/client-imports", tags=["intake"])

INTAKE = "client.intake"
IMPORT = "client_import.run"


def _payload_in(payload: ClientIntakeDraftPayload | None) -> dict[str, object]:
    return {} if payload is None else payload.model_dump(mode="json", exclude_none=True)


def _draft_out(d: intake_model.IntakeDraftView) -> ClientIntakeDraftOut:
    return ClientIntakeDraftOut(
        id=d.id,
        created_by=d.created_by,
        step=cast(IntakeStep, d.step),
        payload=ClientIntakeDraftPayload.model_validate(d.payload),
        committed_client_id=d.committed_client_id,
        version=d.version,
        saved_at=d.saved_at,
        allowed_actions=[] if d.committed_client_id is not None else [INTAKE],
    )


@dedupe_router.post("/dedupe", action="client.create", response_model=DedupeOut)
async def dedupe_route(body: DedupeIn, ctx: Ctx) -> DedupeOut:
    """CLI-06 b: "96% match · Walter Thornbury" (DEC-441); walled clients are never candidates."""
    await _gate(ctx, "client.create")
    found = await dedupe_candidates(ctx, body.name)
    return DedupeOut(
        candidates=[
            DedupeCandidateOut(
                client_id=m.client_id,
                display_name=m.display_name,
                client_entity_id=m.client_entity_id,
                entity_name=m.entity_name,
                score=m.score,
                basis=cast(MatchBasis, m.basis),
            )
            for m in found
        ]
    )


@client_intake_drafts_router.post(
    "", action=INTAKE, response_model=ClientIntakeDraftOut, status_code=201
)
async def create_intake_draft_route(body: ClientIntakeDraftIn, ctx: Ctx) -> ClientIntakeDraftOut:
    """422 `tin_kind_not_allowed`: an SSN or ITIN in the draft's text on a real firm (OQ-4)."""
    await _gate(ctx, INTAKE)
    return _draft_out(await intake_model.create_draft(ctx, body.step, _payload_in(body.payload)))


@client_intake_drafts_router.get("/{draft_id}", action=INTAKE, response_model=ClientIntakeDraftOut)
async def get_intake_draft_route(draft_id: UUID, ctx: Ctx) -> ClientIntakeDraftOut:
    """The owner's draft only (another person's answers 404)."""
    await _gate(ctx, INTAKE)
    return _draft_out(await intake_model.get_draft(ctx, draft_id))


@client_intake_drafts_router.patch(
    "/{draft_id}", action=INTAKE, response_model=ClientIntakeDraftOut, errors=(409,)
)
async def update_intake_draft_route(
    draft_id: UUID, body: ClientIntakeDraftPatchIn, ctx: Ctx
) -> ClientIntakeDraftOut:
    """Autosave; 409 `stale_version`; 422 `tin_kind_not_allowed`."""
    await _gate(ctx, INTAKE)
    return _draft_out(
        await intake_model.update_draft(
            ctx,
            draft_id,
            body.seen_version,
            step=body.step,
            payload=None if body.payload is None else _payload_in(body.payload),
        )
    )


@client_intake_drafts_router.delete(
    "/{draft_id}", action=INTAKE, response_model=ClientIntakeDraftDiscardedOut
)
async def discard_intake_draft_route(draft_id: UUID, ctx: Ctx) -> ClientIntakeDraftDiscardedOut:
    await _gate(ctx, INTAKE)
    at = await intake_model.discard_draft(ctx, draft_id)
    return ClientIntakeDraftDiscardedOut(draft_id=draft_id, discarded_at=at)


@client_intake_drafts_router.post(
    "/{draft_id}/validate", action=INTAKE, response_model=IntakeValidationOut
)
async def validate_intake_draft_route(
    draft_id: UUID, body: IntakeValidateIn, ctx: Ctx
) -> IntakeValidationOut:
    """CLI-06 i: "Required for Form 706 due date" is `date_of_death_required`."""
    await _gate(ctx, INTAKE)
    problems = await intake_model.validate_draft(ctx, draft_id, body.step)
    return IntakeValidationOut(
        draft_id=draft_id,
        step=body.step,
        valid=not problems,
        problems=[IntakeProblemOut(field=p.field, code=p.code) for p in problems],
    )


@client_intake_drafts_router.post(
    "/{draft_id}/commit",
    action=INTAKE,
    response_model=IntakeCommittedOut,
    status_code=201,
    errors=(409,),
)
async def commit_intake_draft_route(
    draft_id: UUID, body: IntakeCommitIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeCommittedOut:
    """Human-only, one unit of work, Prospect engagements only (OQ-2); 409 `gate_unmet` without
    a cleared conflict check, 409 `possible_duplicate`, 422 `draft_incomplete`; a replayed key
    answers the same."""
    await _gate(ctx, INTAKE)
    await intake_model.check_commit(ctx, draft_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await intake_model.commit_intake(ctx, draft_id, body.start_acceptance)
        out = IntakeCommittedOut(
            draft_id=made.draft_id,
            client_id=made.client_id,
            client_entity_id=made.client_entity_id,
            engagement_ids=made.engagement_ids,
            engagement_status=EngagementStatus(made.engagement_status),
            work_item_ids=made.work_item_ids,
            conflict_check_id=made.conflict_check_id,
            acceptance_record_id=made.acceptance_record_id,
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="client_intake_drafts.commit",
        key=idempotency_key,
        body={"draft_id": str(draft_id), **body.model_dump(mode="json")},
        run=run,
    )
    return IntakeCommittedOut.model_validate(stored.body)


def _import_out(v: client_import.ImportView) -> ClientImportOut:
    c = v.counts
    return ClientImportOut(
        id=v.id,
        source=cast(ImportSource, v.source),
        stage=cast(ImportStage, v.stage),
        file_name=v.file_name,
        mapping=v.mapping,
        counts=ClientImportCountsOut(
            rows=c.rows,
            matched=c.matched,
            to_review=c.to_review,
            new=c.new,
            skipped=c.skipped,
            imported=c.imported,
            failed=c.failed,
        ),
        started_by=v.started_by,
        started_at=v.started_at,
        completed_at=v.completed_at,
        allowed_actions=[IMPORT] if v.runnable else [],
    )


def _row_out(r: client_import.RowView) -> ClientImportRowOut:
    return ClientImportRowOut(
        id=r.id,
        row_no=r.row_no,
        display_name=r.display_name,
        entity_type=r.entity_type,
        tin=(
            MaskedTinOut(kind=cast(TinKind, r.tin_kind), presence="on_file", last4=r.tin_last4)
            if r.tin_kind is not None
            else None
        ),
        best_match_client_id=r.best_match_client_id,
        best_match_name=r.best_match_name,
        score=r.score,
        decision=cast(RowDecision | None, r.decision),
        decided_by=r.decided_by,
        error_code=r.error_code,
    )


async def _file(request: Request) -> bytes:
    """The raw body, read up to the parser's bound (a larger one is refused before it is all
    read)."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_IMPORT_BYTES:
            raise client_import.ImportFileRefused(facts={"reason": "file_too_large"})
    return bytes(data)


@client_imports_router.post("", action=IMPORT, response_model=ClientImportOut, status_code=201)
async def upload_client_import_route(
    request: Request,
    ctx: Ctx,
    source: Annotated[ImportSource, Query()],
    filename: Annotated[SingleLineText, Query(min_length=1, max_length=255)],
) -> ClientImportOut:
    """The file is the raw request body (SPEC-008 D3), refused before it is read without the
    action; 422 `import_file_invalid` (`facts.reason`) for a file the import can't read."""
    await _gate(ctx, IMPORT)
    content = await _file(request)
    return _import_out(await client_import.upload_import(ctx, source, filename, content))


@client_imports_router.get("/{import_id}", action=IMPORT, response_model=ClientImportOut)
async def get_client_import_route(import_id: UUID, ctx: Ctx) -> ClientImportOut:
    await _gate(ctx, IMPORT)
    return _import_out(await client_import.get_import(ctx, import_id))


@client_imports_router.get("/{import_id}/rows", action=IMPORT, response_model=ClientImportRowsOut)
async def client_import_rows_route(
    import_id: UUID,
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    review: bool = False,
) -> ClientImportRowsOut:
    """CLI-06 g's table; `review` keeps only the rows waiting for a person. TINs masked for an
    offshore reader (AC9.4)."""
    await _gate(ctx, IMPORT)
    page = await client_import.import_rows(
        ctx, import_id, cursor=cursor, limit=limit, review=review
    )
    rows = ClientImportRowsOut(
        items=[_row_out(r) for r in page.items], next_cursor=page.next_cursor, total=page.total
    )
    return await mask_tins_for(ctx, rows)


@client_imports_router.put(
    "/{import_id}/rows/{row_id}/decision",
    action=IMPORT,
    response_model=ClientImportRowOut,
    errors=(409,),
)
async def decide_import_row_route(
    import_id: UUID, row_id: UUID, body: RowDecisionIn, ctx: Ctx
) -> ClientImportRowOut:
    """A person's decision on a row (never a merge below 90% without one); 409
    `import_already_run`; 422 `import_row_invalid`. TINs masked for an offshore reader (AC9.4)."""
    await _gate(ctx, IMPORT)
    row = await client_import.decide_row(
        ctx, import_id, row_id, body.decision, body.merge_client_id
    )
    return await mask_tins_for(ctx, _row_out(row))


@client_imports_router.post(
    "/{import_id}/run",
    action=IMPORT,
    response_model=ClientImportOut,
    status_code=202,
    errors=(409,),
)
async def run_client_import_route(
    import_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ClientImportOut:
    """Starts `ClientImportWorkflow`; every row applied idempotently; a replayed key answers the
    same; 409 `import_already_run`."""
    await _gate(ctx, IMPORT)

    async def run() -> tuple[int, dict[str, object]]:
        started = await client_import.run_import(ctx, import_id)
        return 202, _import_out(started).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="client_imports.run",
        key=idempotency_key,
        body={"import_id": str(import_id)},
        run=run,
    )
    return ClientImportOut.model_validate(stored.body)
