"""The firm's Schedule H line mapping, as content (A-05-T62 close; S31; TASK-6228; DEC-2823).

EBP-07's tie-out sums the financial statements' captions into Schedule H lines through
`ebp_schedule_h_mappings`: one row per caption, versioned, effective from a plan year, read only
when published (0665; insert-only). The mapping is firm content, so it arrives through this
import, never a seed or a constant: a dry run reports problems by code and place, then a person
with a fresh second factor publishes the whole version at once, and the next tie-out reads it.
When the Form 5500 instructions move a line, a new version follows; an old one never changes.

Route: `POST /v1/ebp/schedule-h-mappings:publish` (`ebp_schedule_h_mapping.publish`).
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)

SUBJECT: Final = "ebp_schedule_h_mapping"
_CAPTION: Final = re.compile(r"^[a-z0-9_.-]{1,80}$")
_LINE: Final = re.compile(r"^[0-9a-z()]{1,20}$")
Ctx = Annotated[AuthContext, Depends(current_context)]


class MappingRowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fs_caption_key: Annotated[str, Field(max_length=80), classified("internal")]
    schedule_h_line: Annotated[str, Field(max_length=20), classified("internal")]


class MappingPublishIn(BaseModel):
    """A whole mapping version: every caption the firm's statements map, with its line."""

    model_config = ConfigDict(extra="forbid")

    effective_plan_year: Annotated[int, Field(ge=2000, le=2100), classified("internal")]
    rows: Annotated[
        list[MappingRowIn], Field(min_length=1, max_length=400), classified("internal")
    ]


class MappingPublishedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int | None, classified("internal")]
    rows: Annotated[int, classified("internal")]
    dry_run: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]
    status: Annotated[Literal["validated", "published", "refused"], classified("internal")]


def problems_of(body: MappingPublishIn) -> list[str]:
    """Codes with where they are, never a value."""
    found: list[str] = []
    seen: set[str] = set()
    for n, row in enumerate(body.rows):
        if not _CAPTION.fullmatch(row.fs_caption_key):
            found.append(f"caption_key_invalid@rows.{n}")
        if not _LINE.fullmatch(row.schedule_h_line):
            found.append(f"schedule_h_line_invalid@rows.{n}")
        if row.fs_caption_key in seen:
            found.append(f"duplicate_caption@rows.{n}")
        seen.add(row.fs_caption_key)
    return found


# Two publishes at once would take the same version: one firm-wide lock per tenant serialises them
# (S31 close end pass security review).
_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_NEXT = text("SELECT COALESCE(max(version), 0) + 1 FROM ebp_schedule_h_mappings")
_ROW = text(
    """
    INSERT INTO ebp_schedule_h_mappings (tenant_id, version, fs_caption_key, schedule_h_line,
        effective_plan_year, published_at, published_by)
    VALUES (:t, :v, :caption, :line, :year, clock_timestamp(), :by)
    """
)


async def publish_mapping(
    ctx: AuthContext, body: MappingPublishIn, *, dry_run: bool
) -> MappingPublishedOut:
    """Dry run first; publishing needs a person, `ebp_schedule_h_mapping.publish` and a fresh
    second factor (the matrix's `mfa_recent`). The version is the next one, firm-wide."""
    if ctx.client:
        raise NotFound(SUBJECT)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden("ebp_schedule_h_mapping.publish", "role")
    await authorise(ctx, "ebp_schedule_h_mapping.publish", Resource.firm(ctx.tenant_id))
    found = problems_of(body)
    if found or dry_run:
        return MappingPublishedOut(
            version=None,
            rows=len(body.rows),
            dry_run=dry_run,
            problems=found,
            status="refused" if found else "validated",
        )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_LOCK, {"key": f"ebp_schedule_h_mappings:{ctx.tenant_id}"})
        version = int(await tx.session.scalar(_NEXT) or 1)
        for row in body.rows:
            await tx.session.execute(
                _ROW,
                {
                    "t": ctx.tenant_id,
                    "v": version,
                    "caption": row.fs_caption_key,
                    "line": row.schedule_h_line,
                    "year": body.effective_plan_year,
                    "by": ctx.user_id,
                },
            )
        tx.record(
            "ebp_schedule_h_mapping.published",
            target=Target(SUBJECT, version),
            after=Ref(version=version, rows=len(body.rows), year=body.effective_plan_year),
        )
    return MappingPublishedOut(
        version=version, rows=len(body.rows), dry_run=False, problems=[], status="published"
    )


schedule_h_mappings_router = AbacusRouter(prefix="/v1/ebp", tags=["assurance"])


@schedule_h_mappings_router.post(
    "/schedule-h-mappings:publish",
    action="ebp_schedule_h_mapping.publish",
    status_code=201,
    response_model=MappingPublishedOut,
)
async def schedule_h_mapping_publish_route(
    body: MappingPublishIn, ctx: Ctx, dry_run: bool = True
) -> MappingPublishedOut:
    """The firm's Schedule H line mapping, a whole version; dry run first."""
    return await publish_mapping(ctx, body, dry_run=dry_run)


__all__ = [
    "MappingPublishIn",
    "MappingPublishedOut",
    "MappingRowIn",
    "problems_of",
    "publish_mapping",
    "schedule_h_mappings_router",
]
