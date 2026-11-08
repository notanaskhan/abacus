"""A-07-T22 (TASK-6206; DEC-2806): the firm's assurance checklists as content (AGENTS 16).

The completion (AUD-19), EQR (AUD-18) and archive (AUD-25) checklists are firm content: a firm
imports a version per (kind, engagement type, name) and a person publishes it with fresh MFA; a
published version never changes (0741's trigger). A completion item carries what the projector
needs: its gate tag, whether it depends on the client, whether it falls due on the report date,
and whether code derives it (a manual item is the only kind a manager may mark not applicable).
No checklist wording lives in code or a migration.

Routes: `POST /v1/methodology/assurance-checklists:import` (JSON body, dry run first) and
`POST /v1/methodology/assurance-checklists/{template_id}/versions/{version}/publish`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)

SUBJECT: Final = "assurance_checklist_template"
ChecklistKind = Literal["completion", "eqr", "archive"]
Internal = classified("internal")
Confidential = classified("confidential")
Ctx = Annotated[AuthContext, Depends(current_context)]


class ChecklistItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,60}$"), Internal]
    text: Annotated[str, Field(min_length=1, max_length=300), Confidential]
    gate_tag: Annotated[str | None, Field(pattern=r"^G[1-9]$"), Internal] = None
    depends_on_client: Annotated[bool, Internal] = False
    due_on_report_date: Annotated[bool, Internal] = False
    derived: Annotated[bool, Internal] = True
    type_specific: Annotated[bool, Internal] = False


class ChecklistImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Annotated[ChecklistKind, Internal]
    engagement_type: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$"), Internal]
    name: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    items: Annotated[list[ChecklistItemIn], Field(min_length=1, max_length=60), Confidential]


class ChecklistImportedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID | None, Internal]
    version: Annotated[int | None, Internal]
    dry_run: Annotated[bool, Internal]
    problems: Annotated[list[str], Internal]


class ChecklistPublishedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    status: Annotated[Literal["published"], Internal]
    published_at: Annotated[datetime, Internal]


class ChecklistVersionPublished(DomainConflict):
    """A published version never changes: import the next one."""

    code = "version_published"


@dataclass(frozen=True)
class PublishedChecklist:
    version_id: UUID
    items: tuple[ChecklistItemIn, ...]


def problems_of(body: ChecklistImportIn) -> list[str]:
    """Codes with where they are, never an item's text."""
    found: list[str] = []
    keys = [i.key for i in body.items]
    for n, key in enumerate(keys):
        if keys.index(key) != n:
            found.append(f"duplicate_key@items.{n}")
    if body.kind != "completion":
        for n, item in enumerate(body.items):
            if item.gate_tag or item.depends_on_client or item.due_on_report_date:
                found.append(f"completion_fields_on_{body.kind}@items.{n}")
    return found


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def import_assurance_checklist(
    ctx: AuthContext, body: ChecklistImportIn, *, dry_run: bool
) -> ChecklistImportedOut:
    action = f"{SUBJECT}.import"
    _person(ctx, action)
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    problems = problems_of(body)
    if problems or dry_run:
        return ChecklistImportedOut(
            template_id=None, version=None, dry_run=dry_run, problems=problems
        )
    items = [i.model_dump() for i in body.items]
    payload = json.dumps(items, sort_keys=True)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"{SUBJECT}:{body.kind}:{body.engagement_type}:{body.name}"},
        )
        template_id = (
            await tx.session.execute(
                text(
                    "SELECT id FROM assurance_checklist_templates "
                    "WHERE kind = :k AND engagement_type = :e AND name = :n"
                ),
                {"k": body.kind, "e": body.engagement_type, "n": body.name},
            )
        ).scalar_one_or_none()
        if template_id is None:
            template_id = (
                await tx.session.execute(
                    text(
                        "INSERT INTO assurance_checklist_templates (tenant_id, kind, "
                        "engagement_type, name, created_by) VALUES (:t, :k, :e, :n, :by) "
                        "RETURNING id"
                    ),
                    {
                        "t": ctx.tenant_id,
                        "k": body.kind,
                        "e": body.engagement_type,
                        "n": body.name,
                        "by": ctx.user_id,
                    },
                )
            ).scalar_one()
        version = (
            await tx.session.execute(
                text(
                    "SELECT coalesce(max(version), 0) + 1 FROM "
                    "assurance_checklist_template_versions WHERE template_id = :t"
                ),
                {"t": template_id},
            )
        ).scalar_one()
        await tx.session.execute(
            text(
                "INSERT INTO assurance_checklist_template_versions (tenant_id, template_id, "
                "version, items, source_file_sha256, imported_by) VALUES (:tenant, :t, :v, "
                "CAST(:items AS jsonb), :sha, :by)"
            ),
            {
                "tenant": ctx.tenant_id,
                "t": template_id,
                "v": version,
                "items": payload,
                "sha": hashlib.sha256(payload.encode()).hexdigest(),
                "by": ctx.user_id,
            },
        )
        tx.record(
            "assurance_checklist_template.imported",
            target=Target(SUBJECT, template_id),
            after=Ref(version=int(version), items=len(items)),
        )
    return ChecklistImportedOut(
        template_id=template_id, version=int(version), dry_run=False, problems=[]
    )


async def publish_assurance_checklist(
    ctx: AuthContext, template_id: UUID, version: int
) -> ChecklistPublishedOut:
    action = f"{SUBJECT}.publish"
    _person(ctx, action)
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT id, status FROM assurance_checklist_template_versions "
                    "WHERE template_id = :t AND version = :v FOR UPDATE"
                ),
                {"t": template_id, "v": version},
            )
        ).first()
        if row is None:
            raise NotFound("assurance_checklist_template_version")
        if row.status == "published":
            raise ChecklistVersionPublished(facts={"version": version})
        published_at = (
            await tx.session.execute(
                text(
                    "UPDATE assurance_checklist_template_versions SET status = 'published', "
                    "published_by = :by, published_at = clock_timestamp() WHERE id = :id "
                    "RETURNING published_at"
                ),
                {"by": ctx.user_id, "id": row.id},
            )
        ).scalar_one()
        tx.record(
            "assurance_checklist_template.published",
            target=Target(SUBJECT, template_id),
            after=Ref(version=version),
        )
    return ChecklistPublishedOut(
        template_id=template_id, version=version, status="published", published_at=published_at
    )


_LATEST = text(
    """
    SELECT v.id, v.items FROM assurance_checklist_template_versions v
      JOIN assurance_checklist_templates t ON t.id = v.template_id
     WHERE t.kind = :k AND t.engagement_type = :e AND v.status = 'published'
     ORDER BY v.published_at DESC, v.version DESC LIMIT 1
    """
)


async def published_checklist(
    tenant: TenantContext, kind: ChecklistKind, engagement_type: str
) -> PublishedChecklist | None:
    """The newest published version for the firm, or None (the projector then lists nothing)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LATEST, {"k": kind, "e": engagement_type})).first()
    if row is None:
        return None
    stored: object = row.items
    raw = cast(list[object], stored if isinstance(stored, list) else json.loads(str(stored)))
    return PublishedChecklist(row.id, tuple(ChecklistItemIn.model_validate(i) for i in raw))


assurance_checklists_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])


@assurance_checklists_router.post(
    "/assurance-checklists:import",
    action="assurance_checklist_template.import",
    status_code=201,
    response_model=ChecklistImportedOut,
)
async def assurance_checklist_import_route(
    body: ChecklistImportIn, ctx: Ctx, dry_run: bool = True
) -> ChecklistImportedOut:
    """The firm's completion, EQR or archive checklist; dry run first."""
    return await import_assurance_checklist(ctx, body, dry_run=dry_run)


@assurance_checklists_router.post(
    "/assurance-checklists/{template_id}/versions/{version}/publish",
    action="assurance_checklist_template.publish",
    response_model=ChecklistPublishedOut,
    errors=(409,),
)
async def assurance_checklist_publish_route(
    template_id: UUID, version: int, ctx: Ctx
) -> ChecklistPublishedOut:
    """A person publishes with fresh MFA; a published version never changes."""
    return await publish_assurance_checklist(ctx, template_id, version)


__all__ = [
    "ChecklistImportIn",
    "ChecklistItemIn",
    "ChecklistKind",
    "ChecklistVersionPublished",
    "PublishedChecklist",
    "assurance_checklists_router",
    "import_assurance_checklist",
    "problems_of",
    "publish_assurance_checklist",
    "published_checklist",
]
