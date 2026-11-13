"""WB-01's session list, blank create, rename and delete (W-02-T09; W-02 §3.1, §3.2; SPEC-653
AC-L1 to AC-L6, AC-V1 to AC-V3; DEC-87, DEC-43; DEC-4714). Amber.

- **Membership (DEC-87, DEC-4601 Q1).** "All" is the sessions the viewer owns, the sessions
  whose owner shares an office or a team with the viewer (`identity.api.colleagues_of`, W-02-T13)
  and the sessions of the engagements the viewer is on (their own engagement roles), never
  deleted ones. Each
  candidate then goes through `viewer_access` over its `client_scope`: a wall on any client omits
  the row (no count, no "n hidden" anywhere); a client the viewer can't open locks it (metadata
  only: title, owner, state; no thread item, figure or count).
- **Filters.** `mine` the viewer's own; `via_agent` rows whose origin is a schedule, a trigger,
  a saved prompt or an engagement run; `running`; `needs_answer`. The counts (`running`,
  `needs_answer`) are over the viewer's visible rows, whatever the filter.
- **Search** matches titles only (`q`, case-insensitive substring; never thread content).
- **Order** newest activity first; 50 a page; the cursor is the next offset.
- **Rename and delete** are the owner's (anyone else 403, AC-L5). Rename checks `If-Match`
  against the row's version (a hash of its title and rename time; 409 `stale_version`), sets
  `title_source = manual` and records `workbench_session.renamed` with title hashes only. Delete is
  soft (`deleted_at`, `deleted_by`): items, runs and trace stay; `workbench_session.deleted`.
- **Blank create** opens a firm-wide, read-only session "New session" (`title_source` auto) for
  the viewer (AC-C1); the first message names it (AC-L6, P-10's post).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    colleagues_of,
    display_names,
    my_engagement_roles,
)
from abacus.modules.workbench.sessions import open_session, viewer_access

PAGE: Final = 50
NEW_TITLE: Final = "New session"
# DEC-4601 Q1: "Via Agent" is every origin that is not `manual`.
VIA_AGENT: Final = frozenset({"schedule", "trigger", "saved_prompt", "engagement_run", "test"})
Filter = Literal["all", "mine", "via_agent", "running", "needs_answer"]


class StaleVersion(DomainConflict):
    """The session changed since the person read it (rename's `If-Match`)."""

    code = "stale_version"


class NotSessionOwner(DomainForbidden):
    """Rename, delete and context belong to the session's owner (AC-L5)."""

    code = "not_session_owner"


@dataclass(frozen=True)
class Row:
    id: UUID
    title: str
    owner_user_id: UUID
    owner_name: str
    origin: str
    state: str
    last_item_at: datetime | None
    title_source: str
    locked: bool
    version: str

    @property
    def via_agent(self) -> bool:
        return self.origin in VIA_AGENT

    @property
    def running(self) -> bool:
        return self.state == "running"

    @property
    def needs_answer(self) -> bool:
        return self.state == "awaiting_answer"

    @property
    def ready_for_review(self) -> bool:
        return self.state == "ready_for_review"


@dataclass(frozen=True)
class Listed:
    rows: tuple[Row, ...]
    total: int
    running: int
    needs_answer: int
    next_cursor: str | None


def version_of(title: str, renamed_at: datetime | None) -> str:
    stamp = "" if renamed_at is None else renamed_at.isoformat()
    return hashlib.sha256(f"{title}|{stamp}".encode()).hexdigest()[:16]


def _title_hash(title: str) -> str:
    return hashlib.sha256(title.encode()).hexdigest()


_CANDIDATES: Final = text(
    "SELECT id, title, owner_user_id, origin, state, last_item_at, client_scope, context_refs, "
    "title_source, renamed_at, created_at FROM workbench_sessions s WHERE deleted_at IS NULL AND "
    "(owner_user_id = :me OR owner_user_id = ANY(:colleagues) OR EXISTS (SELECT 1 FROM "
    "jsonb_array_elements(s.context_refs) r WHERE r->>'kind' = 'engagement' AND "
    "r->>'id' = ANY(CAST(:engagements AS text[])))) "
    "ORDER BY coalesce(last_item_at, created_at) DESC, id LIMIT 2000"
)


def matches(row: Row, filter_: Filter, q: str | None, me: UUID) -> bool:
    if q is not None and q.casefold() not in row.title.casefold():
        return False
    if filter_ == "mine":
        return row.owner_user_id == me
    if filter_ == "via_agent":
        return row.via_agent
    if filter_ == "running":
        return row.running
    if filter_ == "needs_answer":
        return row.needs_answer
    return True


async def list_sessions(
    ctx: AuthContext, filter_: Filter = "all", q: str | None = None, cursor: str | None = None
) -> Listed:
    """The viewer's rows (module docstring). The route authorised `session.read` at the firm."""
    engagements = [str(e) for e in await my_engagement_roles(ctx.tenant, ctx.user_id)]
    # W-02-T13 (DEC-4717): colleagues share an office or a team (S41 CI fix: the parameter the
    # query names was never passed, DEC-4735).
    colleagues = list(await colleagues_of(ctx.tenant, ctx.user_id))
    async with tenant_session(ctx.tenant) as session:
        raw = (
            (
                await session.execute(
                    _CANDIDATES,
                    {"me": ctx.user_id, "colleagues": colleagues, "engagements": engagements},
                )
            )
            .mappings()
            .all()
        )
    names = await display_names(list({r["owner_user_id"] for r in raw}))
    visible: list[Row] = []
    for r in raw:
        access = await viewer_access(ctx, list(r["client_scope"] or []))
        if access == "omitted":
            continue  # walled: no row, no count (DEC-43)
        visible.append(
            Row(
                id=r["id"],
                title=str(r["title"]),
                owner_user_id=r["owner_user_id"],
                owner_name=names.get(r["owner_user_id"], ""),
                origin=str(r["origin"]),
                state=str(r["state"]),
                last_item_at=r["last_item_at"],
                title_source=str(r["title_source"] or "auto"),
                locked=access == "locked",
                version=version_of(str(r["title"]), r["renamed_at"]),
            )
        )
    running = sum(1 for v in visible if v.running)
    needs = sum(1 for v in visible if v.needs_answer)
    chosen = [v for v in visible if matches(v, filter_, q, ctx.user_id)]
    start = int(cursor) if cursor is not None and cursor.isdigit() else 0
    page = chosen[start : start + PAGE]
    following = str(start + PAGE) if start + PAGE < len(chosen) else None
    return Listed(tuple(page), len(chosen), running, needs, following)


async def create_blank(ctx: AuthContext) -> UUID:
    """A firm-wide, read-only session for the viewer (AC-C1)."""
    return await open_session(ctx, title=NEW_TITLE, origin="manual")


_OWNED: Final = text(
    "SELECT id, title, owner_user_id, renamed_at, deleted_at FROM workbench_sessions "
    "WHERE id = :id FOR UPDATE"
)


async def _owned(tx: UnitOfWork, ctx: AuthContext, session_id: UUID) -> Any:  # noqa: ANN401 -- Any: SQL row
    row = (await tx.session.execute(_OWNED, {"id": session_id})).first()
    if row is None or row.deleted_at is not None:
        raise NotFound("session")
    if row.owner_user_id != ctx.user_id:
        raise NotSessionOwner(facts={"session_id": str(session_id)})
    return row


async def rename_session(
    ctx: AuthContext, session_id: UUID, title: str, if_match: str
) -> tuple[Row, str]:
    """The owner's rename (module docstring). Answers the row and its new version."""
    clean = " ".join(title.split())[:200]
    if not clean:
        raise StaleVersion(facts={"reason": "empty_title"})
    async with uow(ctx.tenant) as tx:
        row = await _owned(tx, ctx, session_id)
        current = version_of(str(row.title), row.renamed_at)
        if if_match.strip('"') != current:
            raise StaleVersion(facts={"version": current})
        renamed = await tx.session.scalar(
            text(
                "UPDATE workbench_sessions SET title = :title, title_source = 'manual', "
                "renamed_by = :me, renamed_at = clock_timestamp() WHERE id = :id "
                "RETURNING renamed_at"
            ),
            {"title": clean, "me": ctx.user_id, "id": session_id},
        )
        tx.record(
            "workbench_session.renamed",
            target=Target("workbench_session", session_id),
            before=Ref(title_hash=_title_hash(str(row.title))),
            after=Ref(title_hash=_title_hash(clean)),
        )
    listed = await list_sessions(ctx, "mine")
    found = next((r for r in listed.rows if r.id == session_id), None)
    if found is None:
        raise NotFound("session")
    return found, version_of(clean, renamed)


async def delete_session(ctx: AuthContext, session_id: UUID) -> datetime:
    """Soft delete (module docstring)."""
    async with uow(ctx.tenant) as tx:
        await _owned(tx, ctx, session_id)
        deleted = await tx.session.scalar(
            text(
                "UPDATE workbench_sessions SET deleted_at = clock_timestamp(), deleted_by = :me "
                "WHERE id = :id RETURNING deleted_at"
            ),
            {"me": ctx.user_id, "id": session_id},
        )
        tx.record(
            "workbench_session.deleted",
            target=Target("workbench_session", session_id),
            after=Ref(by=ctx.user_id),
        )
    return deleted


def counts_of(rows: Sequence[Row]) -> tuple[int, int]:
    return sum(1 for r in rows if r.running), sum(1 for r in rows if r.needs_answer)


__all__ = [
    "NEW_TITLE",
    "PAGE",
    "VIA_AGENT",
    "Listed",
    "NotSessionOwner",
    "Row",
    "StaleVersion",
    "counts_of",
    "create_blank",
    "delete_session",
    "list_sessions",
    "matches",
    "rename_session",
    "version_of",
]
