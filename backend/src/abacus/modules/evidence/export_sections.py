"""Evidence's own export sections and the audit-trail slot (A-01-T19; SPEC-344 §6, §7; DEC-379,
DEC-436). PROTECTED.

Four core sections are read by evidence itself through the slot every module uses
(`register_export_section`): `index` (one row per request), `fulfilments` (which file answers
which request), `review_decisions` (every decision on an included file) and `citations` (verified
citation rows into an included file, never quotes or values; INV-2). Requests may not import
evidence (ADR-008), so the index and fulfilment rows come from evidence's reads of
`requests.api`. `screening` is the agents module's. Each provider reads as the requester
(`member_context`, `visible()`), never writes, and never calls a model.

Cells are literal strings (`literal_cell`): TIN forms masked through `kernel.classification.mask`
(`scrub_tins`), and a leading `=`, `+`, `-`, `@`, tab or carriage return neutralised with an
apostrophe (ADR-052), so no spreadsheet reads a client's text as a formula.

`audit_trail/events.jsonl` comes from the audit trail's reader, registered by the composition root
(`register_export_audit_trail`): audit_trail may import only identity, engagements and platform,
so it cannot fill an evidence slot itself. Each line holds identifiers and the actor grammar only
(DEC-60).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, datetime
from typing import Final, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.tin_patterns import scrub_tins
from abacus.modules.evidence.export_manifest import INDEX_COLUMNS
from abacus.modules.evidence.export_models import EngagementExportContent
from abacus.modules.evidence.export_package import (
    ExportSectionInvalid,
    SectionFile,
    SectionRequest,
    register_export_section,
)
from abacus.modules.evidence.export_selection import Plan, current_plan, plan_selection
from abacus.modules.evidence.models import Citation, ReviewDecision
from abacus.modules.evidence.repository import shown_citation
from abacus.modules.identity.api import AuthContext, member_context, visible

_FORMULA_LEADS: Final = ("=", "+", "-", "@", "\t", "\r")
_SEPARATOR: Final = "; "  # between the paths in one index cell


def literal_cell(value: object) -> str:
    """A CSV or XLSX cell that is always read as text: masked, formula leads neutralised."""
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, datetime | date):
        text = value.isoformat()
    else:
        text = str(value)
    text = scrub_tins(text)
    return f"'{text}" if text.startswith(_FORMULA_LEADS) else text


def section_csv(columns: Sequence[str], rows: Sequence[Sequence[object]]) -> bytes:
    """A section's CSV: a header, then one line per row, every cell `literal_cell` (RFC 4180,
    CRLF, UTF-8 without a byte order mark)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([literal_cell(v) for v in row])
    return buffer.getvalue().encode("utf-8")


async def acting_person(tenant: TenantContext, user_id: UUID) -> AuthContext:
    """The person whose export this is, as they are now (no MFA time: reads only)."""
    ctx = await member_context(tenant.tenant_id, user_id)
    if ctx is None:
        raise ExportSectionInvalid("the requester is no longer a member of the firm")
    return ctx


async def requester(tenant: TenantContext, request: SectionRequest) -> AuthContext:
    return await acting_person(tenant, request.requested_by_user_id)


async def plan_of(tenant: TenantContext, request: SectionRequest) -> tuple[AuthContext, Plan]:
    ctx = await requester(tenant, request)
    plan = current_plan(request.export_id) or await plan_selection(ctx, request)
    return ctx, plan


async def included_versions(tenant: TenantContext, request: SectionRequest) -> frozenset[UUID]:
    """The evidence versions this export holds: the build's plan, else its snapshot. For other
    modules' providers (agents' screening), which may not read evidence's tables."""
    plan = current_plan(request.export_id)
    if plan is not None:
        return plan.version_ids
    async with tenant_session(tenant) as session:
        found = await session.execute(
            select(EngagementExportContent.evidence_version_id).where(
                EngagementExportContent.export_id == request.export_id
            )
        )
        return frozenset(found.scalars().all())


# --- index -------------------------------------------------------------------------------------


async def index_section(tenant: TenantContext, request: SectionRequest) -> list[SectionFile]:
    _ctx, plan = await plan_of(tenant, request)
    rows = [
        (
            f"{r.category_no:02d}",
            r.category,
            f"{r.request_no:02d}",
            r.title,
            r.status_label,
            r.owed_by,
            r.requested_on,
            r.due_on,
            len(r.files),
            _SEPARATOR.join(f.path for f in sorted(r.files, key=lambda f: f.path)),
            r.reviewed_by,
            r.reviewed_on,
        )
        for r in plan.requests
    ]
    return [SectionFile("index.csv", section_csv(INDEX_COLUMNS, rows))]


# --- fulfilments -------------------------------------------------------------------------------

FULFILMENT_COLUMNS: Final = (
    "category_no",
    "request_no",
    "request_item_id",
    "binder_id",
    "evidence_version_id",
    "version_no",
    "review_state",
    "sha256",
    "bytes",
    "path",
)


async def fulfilments_section(tenant: TenantContext, request: SectionRequest) -> list[SectionFile]:
    _ctx, plan = await plan_of(tenant, request)
    rows = [
        (
            f"{r.category_no:02d}",
            f"{r.request_no:02d}",
            r.request_item_id,
            r.binder_id,
            f.evidence_version_id,
            f.version_no,
            f.review_state,
            f.fingerprint,
            f.size_bytes,
            f.path,
        )
        for r in plan.requests
        for f in sorted(r.files, key=lambda f: f.path)
    ]
    return [SectionFile("fulfilments.csv", section_csv(FULFILMENT_COLUMNS, rows))]


# --- review decisions --------------------------------------------------------------------------

DECISION_COLUMNS: Final = (
    "evidence_version_id",
    "request_item_id",
    "decision_id",
    "decision_seq",
    "decision",
    "reason_code",
    "undoes_decision_id",
    "actor_kind",
    "actor_user_id",
    "decided_at",
)


async def review_decisions_section(
    tenant: TenantContext, request: SectionRequest
) -> list[SectionFile]:
    """Every decision row on an included file, undo rows too, in order (notes are left out:
    free text; the decision and its reason code are the record)."""
    ctx, plan = await plan_of(tenant, request)
    versions = sorted(plan.version_ids)
    found: Sequence[ReviewDecision] = []
    if versions:
        async with tenant_session(ctx.tenant) as session:
            found = (
                (
                    await session.execute(
                        select(ReviewDecision)
                        .where(
                            ReviewDecision.evidence_version_id.in_(versions),
                            visible(ctx, "evidence.read", ReviewDecision.engagement_id),
                        )
                        .order_by(
                            ReviewDecision.evidence_version_id,
                            ReviewDecision.decision_seq,
                            ReviewDecision.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
    rows = [
        (
            d.evidence_version_id,
            d.request_item_id,
            d.id,
            d.decision_seq,
            d.decision,
            d.reason_code,
            d.undoes_decision_id,
            d.actor_kind,
            d.actor_id if d.actor_kind == "human" else "",
            d.created_at,
        )
        for d in found
    ]
    return [SectionFile("review_decisions.csv", section_csv(DECISION_COLUMNS, rows))]


# --- citations ---------------------------------------------------------------------------------

CITATION_COLUMNS: Final = (
    "citation_id",
    "n",
    "kind",
    "cited_from_type",
    "cited_from_id",
    "source_type",
    "source_id",
    "source_version",
    "verifier_version",
    "created_by_kind",
    "created_at",
)


async def citations_section(tenant: TenantContext, request: SectionRequest) -> list[SectionFile]:
    """Verified citation rows into an included file (INV-2): identifiers only, never the quote
    or the value."""
    ctx, plan = await plan_of(tenant, request)
    versions = sorted(plan.version_ids)
    found: Sequence[Citation] = []
    if versions:
        async with tenant_session(ctx.tenant) as session:
            found = (
                (
                    await session.execute(
                        select(Citation)
                        .where(
                            Citation.source_type == "evidence_version",
                            Citation.source_id.in_(versions),
                            Citation.verified.is_(True),
                            shown_citation(),
                            Citation.engagement_id == request.engagement_id,
                            visible(ctx, "citation.read", _engagement_of_citation),
                        )
                        .order_by(Citation.source_id, Citation.created_at, Citation.id)
                    )
                )
                .scalars()
                .all()
            )
    rows = [
        (
            c.id,
            c.n,
            c.kind,
            c.cited_from_type,
            c.cited_from_id,
            c.source_type,
            c.source_id,
            c.source_version,
            c.verifier_version,
            c.created_by_kind,
            c.created_at,
        )
        for c in found
    ]
    return [SectionFile("citations.csv", section_csv(CITATION_COLUMNS, rows))]


# Filtered to the export's engagement above, so the column is never NULL where it is read.
_engagement_of_citation = cast(QueryableAttribute[UUID], Citation.engagement_id)


# --- the audit trail ---------------------------------------------------------------------------


class _Person(Protocol):
    @property
    def user_id(self) -> UUID: ...


class _Actor(Protocol):
    @property
    def kind(self) -> str: ...
    @property
    def person(self) -> _Person | None: ...
    @property
    def on_behalf_of(self) -> _Person | None: ...
    @property
    def agent_id(self) -> str | None: ...


class _Target(Protocol):
    @property
    def type(self) -> str: ...
    @property
    def id(self) -> str: ...


class AuditTrailRow(Protocol):
    """What evidence reads of one audit event (`audit_trail`'s row has this shape)."""

    @property
    def seq(self) -> int: ...
    @property
    def effective_at(self) -> datetime: ...
    @property
    def action(self) -> str: ...
    @property
    def actor(self) -> _Actor: ...
    @property
    def target(self) -> _Target: ...


class AuditTrailReader(Protocol):
    def __call__(
        self, ctx: AuthContext, work_item_id: UUID, *, as_of_seq: int | None = None
    ) -> Awaitable[Sequence[AuditTrailRow]]: ...


_audit_trail: AuditTrailReader | None = None


def register_export_audit_trail(reader: AuditTrailReader) -> None:
    """The composition root registers `audit_trail.api.events_for_work_item` (once)."""
    global _audit_trail
    if _audit_trail is not None and _audit_trail is not reader:
        raise RuntimeError("the export audit-trail reader is already registered")
    _audit_trail = reader


def audit_trail_registered() -> bool:
    return _audit_trail is not None


def _person(person: _Person | None) -> str | None:
    return str(person.user_id) if person is not None else None


async def audit_trail_lines(ctx: AuthContext, request: SectionRequest) -> bytes:
    """`audit_trail/events.jsonl`: the work item's events up to `as_of_seq`, as the requester
    reads them, oldest first, one canonical JSON object a line."""
    if _audit_trail is None:
        raise ExportSectionInvalid("no audit-trail reader is registered")
    rows = await _audit_trail(ctx, request.work_item_id, as_of_seq=request.as_of_seq)
    lines: list[str] = []
    for row in sorted(rows, key=lambda r: r.seq):
        if row.seq > request.as_of_seq:
            continue
        line = {
            "seq": row.seq,
            "effective_at": row.effective_at.isoformat(),
            "action": row.action,
            "actor": {
                "kind": row.actor.kind,
                "user_id": _person(row.actor.person),
                "on_behalf_of_user_id": _person(row.actor.on_behalf_of),
                "agent_id": row.actor.agent_id,
            },
            "target": {"type": row.target.type, "id": row.target.id},
        }
        lines.append(json.dumps(line, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


SectionReader = Callable[[TenantContext, SectionRequest], Awaitable[list[SectionFile]]]
EVIDENCE_SECTIONS: Final[dict[str, SectionReader]] = {
    "index": index_section,
    "fulfilments": fulfilments_section,
    "review_decisions": review_decisions_section,
    "citations": citations_section,
}
for _name, _provider in EVIDENCE_SECTIONS.items():
    register_export_section(_name, _provider)
