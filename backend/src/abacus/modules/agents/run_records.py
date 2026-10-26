"""Agent run records (Q-02-T41; TASK-1287; ADR-169 §3, P-47, conflict C-12; SPEC-341 AC-44).

A run record is the decision-relevant facts of one ended specialist run: which capability, spec,
prompt (with the SHA-256 of its text), model, route and region produced it, under which data
boundary basis and provider-terms version, what it was given (input hashes), which records it
read, where its citations point (locators and the SHA-256 of the quoted words, never the words),
how it ended and for whom. It is written once, by the run's own workflow after the terminal
state (`agents.persist_run_record`), never updated, and kept for the engagement's retention, so
it still answers "what produced this proposal" after the raw trace (~30 days, ADR-032) is gone.

`record_sha256` is the SHA-256 of the canonical JSON of every other field. It is not the run
view's `run_record_sha256` (TASK-5000), a read-time fingerprint of the live run row: both are
kept, with their own meanings (DEC-396).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.ai_gateway import ModelCall, UnknownPrompt, model_calls_for, prompt
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.models import AgentRun, AgentRunRecord
from abacus.modules.agents.repository import (
    RunCitationRow,
    RunOutputRows,
    RunWriteRow,
    get_run,
    get_run_record,
    insert_run_record,
    run_outputs,
    run_writes,
)
from abacus.modules.agents.runs import Projection, authorised_run, projection_for
from abacus.modules.agents.workflow_types import CANCELLED
from abacus.modules.identity.api import AuthContext

PERSISTED: Final = "agent_run_record.persisted"
RecordState = Literal["succeeded", "needs_input", "failed", "cancelled"]
# A citation keeps where it points and code's verdict on it, never what it quotes: these keys
# are positions and codes (the handoff models classify them `internal`).
_LOCATOR_KEYS: Final = ("document", "claim", "page", "cell")
_FACT_KEYS: Final = ("verified", "reason", "amount_matches")
_MAX_CODE: Final = 40
# The fields `record_sha256` covers, in the record's own order (ADR-169 §3).
FIELDS: Final = (
    "run_id",
    "tenant_id",
    "engagement_id",
    "work_item_id",
    "capability",
    "spec_version",
    "stage",
    "prompt_ref",
    "prompt_sha256",
    "model",
    "route",
    "region",
    "terms_version",
    "boundary_basis",
    "input_hashes",
    "records_read",
    "citations",
    "outcome",
    "initiator_user_id",
    "started_at",
    "completed_at",
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _plain(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        return {str(k): _plain(v) for k, v in mapping.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in cast("Sequence[object]", value)]
    return value


def record_sha256(fields: Mapping[str, object]) -> str:
    """Sorted keys, UTC instants, no whitespace: the same facts always give the same hash."""
    body = {name: fields[name] for name in FIELDS}
    return hashlib.sha256(
        json.dumps(_plain(body), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _code(value: object) -> object:
    """A locator or fact value: a number, a flag or a short code. Anything else is dropped."""
    if isinstance(value, bool | int) or value is None:
        return value
    if isinstance(value, str) and len(value) <= _MAX_CODE:
        return value
    return None


def scrub_citation(row: RunCitationRow) -> dict[str, object]:
    """Where a citation points and what code found, with the quoted words (and the sheet name,
    client content) kept only as SHA-256 fingerprints."""
    c = row.citation
    quote, sheet = c.get("quote"), c.get("sheet")
    out: dict[str, object] = {
        "source": row.source,
        "record": None
        if row.record_id is None
        else {"type": row.record_type, "id": str(row.record_id)},
        "locator": {k: _code(c[k]) for k in _LOCATOR_KEYS if c.get(k) is not None},
        "quote_sha256": _sha256(quote) if isinstance(quote, str) and quote else None,
        "sheet_sha256": _sha256(sheet) if isinstance(sheet, str) and sheet else None,
    }
    for key in _FACT_KEYS:
        if key in c:
            out[key] = _code(c[key])
    return out


def record_state(run: AgentRun) -> RecordState:
    """ADR-169 §2's legacy map: `failed` with the cancelled code is `cancelled`."""
    if run.status == "completed":
        return "succeeded"
    if run.status == "escalated":
        return "needs_input"
    return "cancelled" if run.failure_code == CANCELLED else "failed"


def _subject(run: AgentRun) -> tuple[str, UUID] | None:
    if run.evidence_version_id is not None:
        return ("evidence_version", run.evidence_version_id)
    if run.inbox_file_id is not None:
        return ("inbox_file", run.inbox_file_id)
    if run.methodology_version_id is not None:
        return ("template_version", run.methodology_version_id)
    return None


def _decisive(calls: Sequence[ModelCall]) -> ModelCall | None:
    """The call whose answer the run kept: the last that succeeded, else the last made."""
    kept = [c for c in calls if c.outcome in ("ok", "repaired")] or list(calls)
    return kept[-1] if kept else None


def _prompt_sha256(ref: str | None) -> str | None:
    if ref is None:
        return None
    try:
        return prompt(ref).sha256
    except UnknownPrompt:
        return None


def build_record(
    run: AgentRun,
    calls: Sequence[ModelCall],
    outputs: RunOutputRows,
    writes: Sequence[RunWriteRow],
) -> dict[str, object]:
    """Every field of the run's record, and `record_sha256`, from what the run left behind."""
    if run.finished_at is None:
        raise ValueError("a run record is built once the run has ended")
    call = _decisive(calls)
    read: list[tuple[str, UUID]] = []
    subject = _subject(run)
    for ref in ([subject] if subject else []) + outputs.read:
        if ref not in read:
            read.append(ref)
    counts = dict(outputs.counts)
    for w in writes:
        counts[w.kind] = counts.get(w.kind, 0) + 1
    model_inputs = sorted({c.inputs_hash for c in calls})
    fields: dict[str, object] = {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "engagement_id": run.engagement_id,
        "work_item_id": None,  # runs carry no work item yet (P-10)
        "capability": run.agent_id,
        "spec_version": run.spec_version,
        "stage": "shadow" if run.shadow else "live",
        "prompt_ref": call.prompt if call else None,
        "prompt_sha256": _prompt_sha256(call.prompt if call else None),
        "model": call.model if call else None,
        "route": call.route if call else None,
        "region": call.region if call else None,
        "terms_version": call.terms_version if call else None,
        "boundary_basis": call.boundary_basis if call else None,
        "input_hashes": {
            "context": run.context_hash,
            "model_calls": model_inputs,
        },
        "records_read": [{"type": t, "id": str(i)} for t, i in sorted(read, key=str)],
        "citations": [scrub_citation(c) for c in outputs.citations],
        "outcome": {
            "state": record_state(run),
            "failure_code": run.failure_code,
            "outputs": dict(sorted(counts.items())),
        },
        "initiator_user_id": run.initiator_user_id,
        "started_at": run.started_at,
        "completed_at": run.finished_at,
    }
    fields["record_sha256"] = record_sha256(fields)
    return fields


def _system(tenant_id: UUID, run_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"agent-run:{run_id}")


async def persist_run_record(tenant_id: UUID, run_id: UUID) -> str | None:
    """Write the ended run's record once and audit it (`agent_run_record.persisted`, actor
    system, `Ref(record_sha256)`), returning its hash. Repeat-safe: an existing record's hash
    is returned unchanged. A run still running gets none (None)."""
    tenant = _system(tenant_id, run_id)
    async with tenant_session(tenant) as session:
        run = await get_run(session, run_id)
        existing = await get_run_record(session, run_id)
        if run is None:
            raise NotFound("agent_run")
        if existing is not None:
            return existing.record_sha256
        if run.status == "running" or run.finished_at is None:
            return None
        outputs = await run_outputs(session, run_id)
        writes = await run_writes(session, run_id)
    calls = await model_calls_for(tenant, run_id)
    fields = build_record(run, calls, outputs, writes)
    digest = cast(str, fields["record_sha256"])
    try:
        async with uow(tenant) as tx:
            await insert_run_record(tx.session, _plain_json(fields))
            tx.record(
                PERSISTED,
                target=Target("agent_run", run_id),
                after=Ref(record_sha256=digest),
            )
    except IntegrityError:
        # Another attempt wrote it first (one record per run): report that record.
        async with tenant_session(tenant) as session:
            raced = await get_run_record(session, run_id)
        if raced is None:
            raise
        return raced.record_sha256
    return digest


def _plain_json(fields: Mapping[str, object]) -> dict[str, object]:
    """Column values: JSON columns as plain JSON (strings for ids), the rest as they are."""
    json_columns = ("input_hashes", "records_read", "citations", "outcome")
    return {k: _plain(v) if k in json_columns else v for k, v in fields.items()}


def _metadata_citation(citation: Mapping[str, object]) -> dict[str, object]:
    """DEC-87: what a metadata viewer keeps of a citation: its source and code's verdict."""
    kept: dict[str, object] = {k: v for k, v in citation.items() if k in ("source", *_FACT_KEYS)}
    locator: dict[str, object] = {}
    return kept | {"record": None, "locator": locator, "quote_sha256": None, "sheet_sha256": None}


def fields_of(row: AgentRunRecord) -> dict[str, object]:
    """A stored record's covered fields, for recomputing its hash."""
    return {name: getattr(row, name) for name in FIELDS}


@dataclass(frozen=True)
class RunRecord:
    run_id: UUID
    engagement_id: UUID | None
    capability: str
    spec_version: int
    stage: str
    prompt_ref: str | None
    prompt_sha256: str | None
    model: str | None
    route: str | None
    region: str | None
    terms_version: str | None
    boundary_basis: str | None
    input_hashes: dict[str, object]
    records_read: list[dict[str, object]]
    citations: list[dict[str, object]]
    outcome: dict[str, object]
    initiator_user_id: UUID
    started_at: datetime
    completed_at: datetime
    record_sha256: str
    persisted_at: datetime
    projection: Projection


async def record_for(ctx: AuthContext, run_id: UUID) -> RunRecord:
    """The run's record as stored, for a person who may read the run (`agent_run.read` on its
    engagement; walls, shadow and firm-level runs answer 404). 404 until it is persisted. The
    metadata projection (DEC-87) keeps the facts and fingerprints and drops record identifiers
    and citation locators."""
    run = await authorised_run(ctx, run_id)
    async with tenant_session(ctx.tenant) as session:
        row = await get_run_record(session, run.id)
    if row is None or run.engagement_id is None:
        raise NotFound("agent_run_record")
    projection = await projection_for(ctx, run.engagement_id)
    records_read = row.records_read
    citations = row.citations
    if projection == "metadata":
        records_read = [{"type": r.get("type"), "id": None} for r in records_read]
        citations = [_metadata_citation(c) for c in citations]
    return RunRecord(
        row.run_id,
        row.engagement_id,
        row.capability,
        row.spec_version,
        row.stage,
        row.prompt_ref,
        row.prompt_sha256,
        row.model,
        row.route,
        row.region,
        row.terms_version,
        row.boundary_basis,
        row.input_hashes,
        records_read,
        citations,
        row.outcome,
        row.initiator_user_id,
        row.started_at,
        row.completed_at,
        row.record_sha256,
        row.persisted_at,
        projection,
    )


__all__: Sequence[str] = [
    "PERSISTED",
    "RunRecord",
    "build_record",
    "fields_of",
    "persist_run_record",
    "record_for",
    "record_sha256",
    "scrub_citation",
]
