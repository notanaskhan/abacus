"""The render job: a version's sealed snapshot to its files (P-11-T11; P-11 §4.4, §4.6; C11 v1 §2;
DEC-1457, DEC-1561).

`generated_document.render_requested` (emitted with the version, P-11-T08) reaches `run` through
`reporting.api.SUBSCRIPTIONS`. The job reads the version, its sealed snapshot (0522) and the
template version's parts as the system for the version's firm; composes them (`compose.py`);
renders the PDF and its field regions in the isolated child, and the DOCX when the kind asks for
it; stores each file under Object Lock before the unit of work (`evidence.api.store_generated`);
then, in one unit of work, records each file as an evidence version (`files.record_file`, which
marks the job succeeded) and the field-region manifest. The snapshot is never re-resolved: a
source change after the render reaches the document as Out of date (P-11-T08's consumer), and a
person regenerates. A refusal (`missing_glyph`, `unknown_block`, `renderer_unavailable`…) fails
the job with its code and a `render_failed` event, audited, and never leaves a partial file.

Redelivery is a no-op: a job that is not `queued` is left alone.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import RowMapping, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence.api import StoredObject, store_generated
from abacus.modules.methodology.api import report_template_parts
from abacus.modules.reporting import compose
from abacus.modules.reporting.documents import TARGET, add_event, snapshot_of_version
from abacus.modules.reporting.files import record_file
from abacus.modules.reporting.render.core import (
    LocatedOutput,
    Mode,
    render_docx,
    render_located_isolated,
)
from abacus.modules.reporting.render.head import RenderRefused

_log = get_logger(__name__)
ACTOR: Final = "reporting.render_job"
# 0430's `render_jobs.failure_code` values; anything else is reported as the renderer's.
_FAILURE_CODES: Final = frozenset(
    {
        "missing_variable",
        "final_requires_approval",
        "approval_hash_mismatch",
        "markup_not_allowed",
        "unknown_variable",
        "asset_not_allowed",
        "missing_glyph",
        "renderer_unavailable",
        "document_locked",
    }
)
_TITLES: Final = {
    "engagement_letter": "Engagement letter",
    "consent_7216": "Consent to use or disclose tax return information",
    "representation_letter": "Representation letter",
    "governance_letter": "Communication with those charged with governance",
    "audit_report": "Independent auditor's report",
    "review_report": "Independent accountant's review report",
    "compilation_report": "Accountant's compilation report",
    "notice_response": "Notice response",
    "delivery_cover_letter": "Delivery cover letter",
    "k1_cover_letter": "Schedule K-1 cover letter",
    "fs_package": "Financial statements",
    "run_trace_export": "Run trace export",
}


async def _job(system: TenantContext, document_id: UUID, version_no: int) -> RowMapping | None:
    """The queued job's version and document, or None (already run, or unknown)."""
    async with tenant_session(system) as session:
        row = (
            (
                await session.execute(
                    text(
                        "SELECT v.id AS version_id, v.mode, v.template_version_id, "
                        "v.layout_key, v.content_hash, v.created_at, v.requested_by_user_id, "
                        "v.on_behalf_of_user_id, d.kind, d.client_id, d.engagement_id "
                        "FROM render_jobs j JOIN generated_document_versions v "
                        "ON v.generated_document_id = j.generated_document_id "
                        "AND v.version_no = j.target_version_no "
                        "JOIN generated_documents d ON d.id = j.generated_document_id "
                        "WHERE j.generated_document_id = :d AND j.target_version_no = :n "
                        "AND j.status = 'queued'"
                    ),
                    {"d": document_id, "n": version_no},
                )
            )
            .mappings()
            .first()
        )
    return row


def title_for(kind: str, template_name: str) -> str:
    return template_name or _TITLES.get(kind, "Document")


async def _fail(
    system: TenantContext, row: RowMapping, document_id: UUID, version_no: int, code: str
) -> None:
    failure = code if code in _FAILURE_CODES else "renderer_unavailable"
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE render_jobs SET status = 'failed', failure_code = :c, "
                "finished_at = clock_timestamp() WHERE generated_document_id = :d "
                "AND target_version_no = :n AND status = 'queued'"
            ),
            {"c": failure, "d": document_id, "n": version_no},
        )
        await add_event(
            tx,
            document_id=document_id,
            kind="render_failed",
            cause_ref=f"version:{version_no}:{failure}",
            changed_keys=None,
            actor_kind="system",
            actor_user_id=None,
        )
        tx.record(
            "generated_document.render_failed",
            target=Target(TARGET, document_id),
            after=Ref(version_no=version_no),  # the code is on the job and the event
            scope=Scope(
                engagement_id=cast(UUID | None, row["engagement_id"]),
                client_id=cast(UUID, row["client_id"]),
            ),
        )


async def run(tenant_id: UUID, document_id: UUID, version_no: int) -> None:
    """Render one queued version and record its files (or fail the job with its code)."""
    system = TenantContext(tenant_id, "system", ACTOR)
    row = await _job(system, document_id, version_no)
    if row is None:
        return
    version_id = cast(UUID, row["version_id"])
    kind = str(row["kind"])
    try:
        async with tenant_session(system) as session:
            parts = (
                None
                if row["template_version_id"] is None
                else await report_template_parts(session, cast(UUID, row["template_version_id"]))
            )
            sealed = await snapshot_of_version(session, version_id)
        if parts is None or sealed is None:
            raise RenderRefused("unknown_variable")  # no template version or sealed snapshot
        composition = compose.compose(
            layout_key=str(row["layout_key"]),
            body=parts.body,
            clauses=parts.clauses,
            snapshot=sealed,
        )
        request = compose.render_input(
            composition,
            title=title_for(kind, parts.template_name),
            as_of=cast(datetime, row["created_at"]),
            mode=cast(Mode, str(row["mode"])),
            content_hash=str(row["content_hash"]),
        )
        located = render_located_isolated(request)
        files: list[tuple[str, bytes, str, int]] = [
            ("pdf", located.output.pdf, located.output.render_hash, located.output.page_count)
        ]
        if _wants_docx(kind):
            docx = render_docx(request)
            files.append(("docx", docx.docx, docx.render_hash, located.output.page_count))
    except RenderRefused as refused:
        _log.info("render_job.refused", document_id=str(document_id))  # the code is on the job
        await _fail(system, row, document_id, version_no, refused.code)
        return
    stored: list[tuple[str, StoredObject, str, int]] = [
        (fmt, await store_generated(tenant_id, content), digest, pages)
        for fmt, content, digest, pages in files
    ]
    requested_by = cast(UUID | None, row["requested_by_user_id"] or row["on_behalf_of_user_id"])
    async with uow(system) as tx:
        for fmt, obj, digest, pages in stored:
            await record_file(
                tx,
                document_id=document_id,
                version_no=version_no,
                file_format="pdf" if fmt == "pdf" else "docx",
                stored=obj,
                render_hash=digest,
                page_count=pages,
                title=request.title,
                requested_by=requested_by,
            )
        await _record_regions(tx, tenant_id, version_id, document_id, located, _labels(parts))


def _wants_docx(kind: str) -> bool:
    from abacus.modules.reporting.api import UnknownDocumentKind, document_kind

    try:
        return "docx" in document_kind(kind).formats
    except UnknownDocumentKind:
        return False


def _labels(parts: object) -> Mapping[str, str]:
    variables = cast(tuple[object, ...], getattr(parts, "variables", ()))
    out: dict[str, str] = {}
    for v in variables:
        if isinstance(v, Mapping):
            m = cast(Mapping[str, object], v)
            out[str(m.get("key"))] = str(m.get("label") or m.get("key"))
    return out


async def _record_regions(
    tx: UnitOfWork,
    tenant_id: UUID,
    version_id: UUID,
    document_id: UUID,
    located: LocatedOutput,
    labels: Mapping[str, str],
) -> None:
    for region in located.regions:
        await tx.session.execute(
            text(
                "INSERT INTO generated_document_fields (tenant_id, version_id, field_key, "
                "occurrence, label, page, rect_pt, value_text, match_id) VALUES "
                "(:t, :v, :k, :o, :l, :p, :r, :val, :m)"
            ),
            {
                "t": tenant_id,
                "v": version_id,
                "k": region.field_key,
                "o": region.occurrence,
                "l": labels.get(region.field_key, region.field_key)[:200],
                "p": region.page,
                "r": list(region.rect_pt),
                "val": region.value_text,
                "m": f"gd:{document_id}:{region.field_key}:{region.occurrence}",
            },
        )


async def on_render_requested(event: OutboxEvent) -> None:
    """The relay's delivery of `generated_document.render_requested` (identifiers only)."""
    payload = event.payload
    document_id = UUID(str(payload["generated_document_id"]))
    version_no = int(cast(int, payload["version_no"]))
    await run(event.tenant_id, document_id, version_no)
