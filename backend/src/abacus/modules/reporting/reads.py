"""The generated-document routes and the template preview, live (P-11-T11; P-11 §4.3; C11 v1;
SPEC-520 AC-14, AC-17 to AC-19, AC-22, AC-23, AC-26; DEC-1561).

Every route keeps C11's order: a client principal 404 (clients never reach C11: INV-4; DEC-1561
keeps the frozen 404 over the row's "403"), the `reporting.generated_documents` flag (404 off),
the document read under the firm's row-level security (404 when it is not this firm's), then the
route's one matrix action on the document's own scope: its engagement (team, independence) or,
for a client-level document such as a consent, its client. A walled person gets 404 with no
count; any other refusal is 403.

- **Read** returns the computed status (P-11-T08) and every version with its files, template,
  requester ("<person> via Agent" for an agent's draft, INV-5) and approval.
- **Fields** is the version's field-region manifest (the render job's, 0430).
- **Compare** is a deterministic word diff by block and clause id, against the template's
  standard text for the same values or against another version (`compose.py`).
- **Changes** compares the sealed values with what the kind's provider answers now; a key the
  provider does not answer is not reported (it cannot be told apart from unchanged), and a value
  that looks like a TIN reads `masked` with both sides null.
- **Regenerate** is a person's (`generated_document.regenerate` denies the agent and the system,
  and the route refuses any non-human context first), under `Idempotency-Key`; 409
  `document_locked`.
- **Preview** renders the template version's synthetic sample data with the SAMPLE mark in the
  isolated child and answers the page sizes; nothing is stored and nothing becomes evidence.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import REPORTING_GENERATED_DOCUMENTS
from abacus.kernel.clock import system_now
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import (
    DomainConflict,
    DomainForbidden,
    DomainInvalid,
    DomainUnavailable,
    NotFound,
)
from abacus.kernel.flags import flag_enabled
from abacus.kernel.tin_patterns import has_tin
from abacus.kernel.uow import uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    names_of,
)
from abacus.modules.methodology.api import report_template_parts, report_template_version
from abacus.modules.reporting import compose
from abacus.modules.reporting import documents as docs
from abacus.modules.reporting.contract import (
    BlockDiffOut,
    ChangedVariableOut,
    ChangesOut,
    CompareOut,
    DiffOpOut,
    FieldRegionOut,
    FieldRegionsOut,
    GeneratedDocumentOut,
    PreviewPageOut,
    RenderTicketOut,
    TemplatePreviewOut,
)
from abacus.modules.reporting.render.core import render_located_isolated
from abacus.modules.reporting.render.head import RenderRefused as RenderingRefused
from abacus.modules.reporting.render_job import title_for

READ: Final = "generated_document.read"
REGENERATE: Final = "generated_document.regenerate"
PREVIEW_TTL: Final = timedelta(minutes=15)


class DocumentLocked(DomainConflict):
    code = "document_locked"


class RegenerateRefused(DomainInvalid):
    """The provider has no value for a declared key (`missing_variable`), or no template."""

    code = "missing_variable"


class NotAPerson(DomainForbidden):
    code = "human_only"


class PreviewRefused(DomainInvalid):
    """The sample data does not render (`missing_variable`, `missing_glyph`, …)."""

    code = "preview_refused"


class RendererUnavailable(DomainUnavailable):
    code = "renderer_unavailable"


async def _flag(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("generated documents")
    if not await flag_enabled(ctx.tenant, REPORTING_GENERATED_DOCUMENTS):
        raise NotFound(REPORTING_GENERATED_DOCUMENTS.name)


async def _resource(ctx: AuthContext, doc: RowMapping) -> Resource:
    engagement_id = cast(UUID | None, doc["engagement_id"])
    client_id = cast(UUID, doc["client_id"])
    if engagement_id is None:
        return Resource.client(ctx.tenant_id, client_id)
    found = await engagement_resource(ctx.tenant, engagement_id)
    return replace(found, client_id=client_id, work_item_id=doc["work_item_id"])


async def _allowed(ctx: AuthContext, action: str, doc: RowMapping) -> None:
    try:
        await authorise(ctx, action, await _resource(ctx, doc))
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("generated document") from None  # no count, no hint
        raise


async def _document(ctx: AuthContext, session: AsyncSession, document_id: UUID) -> RowMapping:
    doc = await docs.document_row(session, document_id)
    if doc is None:
        raise NotFound("generated document")
    return doc


async def _gate(
    ctx: AuthContext, session: AsyncSession, document_id: UUID, action: str
) -> RowMapping:
    """The flag was checked before the session opened (`_flag`): no connection for a client."""
    doc = await _document(ctx, session, document_id)
    await _allowed(ctx, action, doc)
    return doc


def _label(kind: str, user: UUID | None, on_behalf: UUID | None, names: dict[UUID, str]) -> str:
    if kind == "agent":
        person = names.get(on_behalf, "") if on_behalf else ""
        return f"{person} via Agent" if person else "Agent"
    if kind == "human":
        return names.get(user, "") if user else ""
    return "System"


async def _can(ctx: AuthContext, action: str, doc: RowMapping) -> bool:
    try:
        await authorise(ctx, action, await _resource(ctx, doc))
    except Forbidden:
        return False
    return True


async def read(ctx: AuthContext, document_id: UUID) -> GeneratedDocumentOut:
    await _flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        doc = await _gate(ctx, session, document_id, READ)
        view = await docs.generated_document(session, document_id)
        versions = (
            (
                await session.execute(
                    text(
                        "SELECT id, version_no, mode, content_hash, snapshot_sha256, "
                        "template_version_id, engine_version, requested_by_kind, "
                        "requested_by_user_id, on_behalf_of_user_id, approval_ref, created_at "
                        "FROM generated_document_versions WHERE generated_document_id = :d "
                        "ORDER BY version_no"
                    ),
                    {"d": document_id},
                )
            )
            .mappings()
            .all()
        )
        files = (
            (
                await session.execute(
                    text(
                        "SELECT f.version_id, f.format, f.evidence_version_id, f.render_hash, "
                        "f.page_count FROM generated_document_files f "
                        "JOIN generated_document_versions v ON v.id = f.version_id "
                        "WHERE v.generated_document_id = :d ORDER BY f.format"
                    ),
                    {"d": document_id},
                )
            )
            .mappings()
            .all()
        )
        templates: dict[UUID, tuple[UUID, int, str]] = {}
        for v in versions:
            tv = cast(UUID | None, v["template_version_id"])
            if tv is not None and tv not in templates:
                parts = await report_template_parts(session, tv)
                if parts is not None and parts.template_id is not None:
                    templates[tv] = (parts.template_id, parts.version_no, parts.template_name)
    if view is None:
        raise NotFound("generated document")
    people: set[UUID] = set()
    for v in versions:
        for key in ("requested_by_user_id", "on_behalf_of_user_id"):
            if v[key] is not None:
                people.add(cast(UUID, v[key]))
        approval = cast(dict[str, str] | None, v["approval_ref"])
        if approval and approval.get("approver_user_id"):
            people.add(UUID(approval["approver_user_id"]))
    names = await names_of(sorted(people)) if people else {}
    by_version: dict[UUID, list[RowMapping]] = {}
    for f in files:
        by_version.setdefault(cast(UUID, f["version_id"]), []).append(f)
    out_versions: list[dict[str, object]] = []
    for v in versions:
        approval = cast(dict[str, str] | None, v["approval_ref"])
        tv = cast(UUID | None, v["template_version_id"])
        tpl = templates.get(tv) if tv is not None else None
        out_versions.append(
            {
                "n": v["version_no"],
                "mode": v["mode"],
                "files": [
                    {
                        "format": f["format"],
                        "evidence_version_id": f["evidence_version_id"],
                        "render_hash": bytes(cast(bytes, f["render_hash"])).hex(),
                        "page_count": f["page_count"],
                    }
                    for f in by_version.get(cast(UUID, v["id"]), [])
                ],
                "content_hash": v["content_hash"],
                "template": None
                if tpl is None
                else {"id": tpl[0], "version_no": tpl[1], "name": tpl[2]},
                "snapshot_sha256": v["snapshot_sha256"],
                "engine_version": v["engine_version"],
                "requested_by": {
                    "kind": v["requested_by_kind"],
                    "label": _label(
                        str(v["requested_by_kind"]),
                        cast(UUID | None, v["requested_by_user_id"]),
                        cast(UUID | None, v["on_behalf_of_user_id"]),
                        names,
                    ),
                },
                "approval": None
                if not approval
                else {
                    "by": names.get(UUID(approval["approver_user_id"]), ""),
                    "at": v["created_at"],
                },
                "created_at": v["created_at"],
            }
        )
    allowed = (
        ["regenerate"]
        if view.status != "locked"
        and ctx.tenant.actor_kind == "human"
        and await _can(ctx, REGENERATE, doc)
        else []
    )
    return GeneratedDocumentOut.model_validate(
        {
            "id": document_id,
            "kind": view.kind,
            "owner_ref": {"type": view.owner_type, "id": view.owner_id},
            "status": view.status,
            "out_of_date": view.out_of_date,
            "out_of_date_reasons": list(view.out_of_date_reasons),
            "current_version": view.current_version,
            "versions": out_versions,
            "allowed_actions": allowed,
        }
    )


async def _version_row(session: AsyncSession, document_id: UUID, version_no: int) -> RowMapping:
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, version_no, layout_key, template_version_id, mode "
                    "FROM generated_document_versions WHERE generated_document_id = :d "
                    "AND version_no = :n"
                ),
                {"d": document_id, "n": version_no},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise NotFound("generated document version")
    return row


async def fields(ctx: AuthContext, document_id: UUID, version_no: int) -> FieldRegionsOut:
    await _flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        await _gate(ctx, session, document_id, READ)
        version = await _version_row(session, document_id, version_no)
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT field_key, label, page, rect_pt, value_text, match_id "
                        "FROM generated_document_fields WHERE version_id = :v "
                        "ORDER BY page, field_key, occurrence"
                    ),
                    {"v": version["id"]},
                )
            )
            .mappings()
            .all()
        )
    return FieldRegionsOut(
        items=[
            FieldRegionOut(
                field_key=str(r["field_key"]),
                label=str(r["label"]),
                page=int(r["page"]),
                rect_pt=[float(x) for x in cast(list[float], r["rect_pt"])],
                value_text=str(r["value_text"]),
                match_id=str(r["match_id"]),
            )
            for r in rows
        ]
    )


async def _composition(
    session: AsyncSession, version: RowMapping
) -> tuple[compose.Composition, compose.Composition]:
    """The version as sealed, and the template's standard text for the same values."""
    tv = cast(UUID | None, version["template_version_id"])
    parts = None if tv is None else await report_template_parts(session, tv)
    sealed = await docs.snapshot_of_version(session, cast(UUID, version["id"]))
    if parts is None or sealed is None:
        raise NotFound("generated document snapshot")
    sealed_c = compose.compose(
        layout_key=str(version["layout_key"]),
        body=parts.body,
        clauses=parts.clauses,
        snapshot=sealed,
    )
    std = compose.standard(
        layout_key=str(version["layout_key"]),
        body=parts.body,
        clauses=parts.clauses,
        values=sealed_c.values,
    )
    return sealed_c, std


async def compare(ctx: AuthContext, document_id: UUID, version_no: int, to: str) -> CompareOut:
    await _flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        await _gate(ctx, session, document_id, READ)
        this, standard = await _composition(
            session, await _version_row(session, document_id, version_no)
        )
        if to == "standard":
            before = standard
        else:
            before, _ = await _composition(
                session, await _version_row(session, document_id, int(to))
            )
    return CompareOut(
        to=to,
        blocks=[
            BlockDiffOut(
                block_id=bid,
                clause_id=cid,
                ops=[DiffOpOut(op=op, text=t) for op, t in ops],
            )
            for bid, cid, ops in compose.compare(before, this)
        ],
    )


async def changes(ctx: AuthContext, document_id: UUID) -> ChangesOut:
    from abacus.modules.reporting import api as c11

    await _flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        doc = await _gate(ctx, session, document_id, READ)
        view = await docs.generated_document(session, document_id)
        if view is None or view.current_version is None:
            return ChangesOut(items=[])
        version = await _version_row(session, document_id, view.current_version)
        sealed = await docs.snapshot_of_version(session, cast(UUID, version["id"]))
        tv = cast(UUID | None, version["template_version_id"])
        parts = None if tv is None else await report_template_parts(session, tv)
    if sealed is None:
        return ChangesOut(items=[])
    was = compose.compose(
        layout_key=str(version["layout_key"]), body=[], clauses=[], snapshot=sealed
    ).values
    try:
        kind = c11.document_kind(view.kind)
    except c11.UnknownDocumentKind:
        return ChangesOut(items=[])
    now = await kind.variables_provider(
        c11.OwnerRef(view.owner_type, view.owner_id),
        c11.RenderScope(
            client_id=cast(UUID, doc["client_id"]),
            engagement_id=cast(UUID | None, doc["engagement_id"]),
            work_item_id=cast(UUID | None, doc["work_item_id"]),
        ),
    )
    labels = _labels(parts.variables if parts is not None else ())
    items: list[ChangedVariableOut] = []
    for key in sorted(was):
        current = now.get(key)
        if current is None or not current.strip() or current == was[key]:
            continue
        masked = has_tin(was[key]) or has_tin(current)
        items.append(
            ChangedVariableOut(
                key=key,
                label=labels.get(key, key),
                was=None if masked else was[key],
                now=None if masked else current,
                masked=masked,
            )
        )
    return ChangesOut(items=items)


def _labels(variables: tuple[object, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for v in variables:
        if isinstance(v, dict):
            m = cast(dict[str, object], v)
            out[str(m.get("key"))] = str(m.get("label") or m.get("key"))
    return out


async def regenerate(ctx: AuthContext, document_id: UUID, idempotency_key: str) -> RenderTicketOut:
    from abacus.modules.reporting import api as c11

    if ctx.client:
        raise NotFound("generated documents")
    if ctx.tenant.actor_kind != "human":
        raise NotAPerson("regenerate is a person's")
    await _flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        doc = await _document(ctx, session, document_id)
    await _allowed(ctx, REGENERATE, doc)

    async def run() -> tuple[int, dict[str, object]]:
        async with uow(ctx.tenant) as tx:
            try:
                ticket = await c11.regenerate(
                    tx, document_id, c11.Requester("human", user_id=ctx.user_id)
                )
            except c11.RenderRefused as refused:
                if refused.code == "document_locked":
                    raise DocumentLocked("the document is locked") from None
                raise RegenerateRefused(str(refused)) from None
        return 200, {
            "generated_document_id": str(ticket.generated_document_id),
            "version_no": ticket.version_no,
        }

    stored = await idempotent(
        ctx.tenant,
        route="generated_document.regenerate",
        key=idempotency_key,
        body={"document_id": str(document_id)},
        run=run,
    )
    response = stored.body
    return RenderTicketOut(
        generated_document_id=UUID(str(response["generated_document_id"])),
        version_no=int(cast(int, response["version_no"])),
    )


async def preview(ctx: AuthContext, template_id: UUID, version_no: int) -> TemplatePreviewOut:
    """SAMPLE render of a template version from its synthetic sample data (AC-7)."""
    if ctx.client:
        raise NotFound("generated documents")
    await authorise(ctx, "report_template.read", Resource.firm(ctx.tenant_id))
    await _flag(ctx)
    view = await report_template_version(ctx, template_id, version_no)
    sample = {str(k): str(v) for k, v in dict(view.sample_data).items()}
    composition = compose.standard(
        layout_key=view.layout_key,
        body=view.body,
        clauses=view.clauses,
        values=sample,
    )
    try:
        located = render_located_isolated(
            compose.render_input(
                composition,
                title=title_for(view.family, ""),
                as_of=system_now(),
                mode="sample",
                content_hash=view.content_sha256,
            )
        )
    except RenderingRefused as refused:
        if refused.code == "renderer_unavailable":
            raise RendererUnavailable("the renderer is unavailable") from None
        raise PreviewRefused(refused.code) from None
    return TemplatePreviewOut(
        pages=[
            PreviewPageOut(n=n, width_pt=size.width_pt, height_pt=size.height_pt)
            for n, size in enumerate(located.page_sizes, start=1)
        ],
        expires_at=system_now() + PREVIEW_TTL,
    )
