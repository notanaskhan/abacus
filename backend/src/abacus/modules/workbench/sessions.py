"""Workbench sessions core (P-10-T43; SPEC-647 §3.7 AC-S1 to AC-S5; P-10 §4.3; DEC-87, DEC-4301).

- **Read** (`GET /v1/workbench/sessions/{id}`): the thread snapshot, `session.read`. The owner
  reads their own; anyone else reads a session only through its engagement (a person who can't
  read that engagement, or a session with none, answers 404). Visibility follows DEC-87 over the
  session's `client_scope`, every client its turns read: a session that read a client the
  viewer is **walled** from is omitted (404); one that read a client the viewer may not open
  answers `locked: true` with no items, so no figure reaches them (AC-S3, WB-01g).
- **Post** (`POST …/messages`, 202): `session.create`, the owner only, never on a locked or
  deleted session, behind the `agent_runtime.v2` kill switch. The person's item and their turn's
  run are written, then the session's workflow is signalled (started if none runs). The same
  `Idempotency-Key` answers the same item. `answers_seq` names an open question: the body is
  the answer, a turn of its own; without it a message is answered first and the question stays
  open (AC-S2).
- **Open** (`open_session`): a session for its owner, with its engagement and capability as
  `context_refs`. The list, create, rename and delete routes are W-02's; P-10-T39's engagement
  dock and T-04-T37's tax assistant open theirs here.

A soft-deleted session keeps its items and runs (AC-S5): it reads 404 and takes no message.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import AGENT_RUNTIME_V2
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import signal_with_start
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import capability_ready, open_turn_run, subject_engagement
from abacus.modules.engagements.api import client_of, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    could,
    display_names,
    firm_role_allows,
    is_synthetic_firm,
    my_engagement_roles,
    walled_from,
)
from abacus.modules.workbench.session_workflow import (
    SessionInput,
    WorkbenchSessionWorkflow,
    session_workflow_id,
)

# A session without a named capability on a synthetic firm talks to the reference loop
# capability; a real firm's session needs one (W-03 definitions, T-04-T37's tax assistant).
SYNTHETIC_DEFAULT: Final = "runtime.conformance"
ITEMS_PAGE: Final = 500

Viewer = Literal["open", "locked", "omitted"]


class CapabilityUnavailable(DomainConflict):
    """DF-04: the session's capability can't run here now (`facts.reason`)."""

    code: ClassVar[str] = "capability_unavailable"


class SessionLocked(DomainConflict):
    """The session read a client the person may not open (DEC-87): it takes no message."""

    code: ClassVar[str] = "session_locked"


@dataclass(frozen=True)
class SessionRow:
    id: UUID
    title: str
    owner_user_id: UUID
    origin: str
    state: str
    context_refs: list[dict[str, str]]
    client_scope: list[UUID]
    last_item_at: datetime | None
    deleted: bool


_SESSION = text(
    "SELECT id, title, owner_user_id, origin, state, context_refs, client_scope, last_item_at, "
    "deleted_at IS NOT NULL AS deleted FROM workbench_sessions WHERE id = :id"
)
_ITEMS = text(
    "SELECT id, seq, kind, payload, run_id, step_id, actor_kind, actor_id, created_at "
    "FROM session_items WHERE session_id = :id ORDER BY seq DESC LIMIT :page"
)


async def load_session(session: AsyncSession, session_id: UUID) -> SessionRow | None:
    row = (await session.execute(_SESSION, {"id": session_id})).first()
    if row is None:
        return None
    return SessionRow(
        id=row.id,
        title=row.title,
        owner_user_id=row.owner_user_id,
        origin=row.origin,
        state=row.state,
        context_refs=cast(list[dict[str, str]], row.context_refs or []),
        client_scope=cast(list[UUID], row.client_scope or []),
        last_item_at=row.last_item_at,
        deleted=bool(row.deleted),
    )


def ref_of(refs: Sequence[Mapping[str, str]], kind: str) -> str | None:
    for ref in refs:
        if ref.get("kind") == kind and ref.get("id"):
            return ref["id"]
    return None


async def _clients_on_team(ctx: AuthContext) -> frozenset[UUID]:
    """The clients of every engagement the viewer is on (their own engagement roles)."""
    found: set[UUID] = set()
    for engagement in await my_engagement_roles(ctx.tenant, ctx.user_id):
        client = await client_of(ctx.tenant, engagement)
        if client is not None:
            found.add(client)
    return frozenset(found)


async def viewer_access(
    ctx: AuthContext, clients: Sequence[UUID], opened: frozenset[UUID] = frozenset()
) -> Viewer:
    """DEC-87 for one viewer over a session's `client_scope` (AC-S3). A wall on any client omits
    the session. A client opens for the viewer through the session's engagement (`opened`), a firm
    role that reads every client, or the viewer's team on one of that client's engagements; any
    other client locks the session (no items, no figures)."""
    if not clients:
        return "open"
    walls = await walled_from(ctx.tenant, ctx.user_id)
    if any(c in walls for c in clients):
        return "omitted"
    rest = [c for c in clients if c not in opened]
    # A firm role (never an engagement role) whose matrix cell reads every client it isn't walled
    # from; identity decides it (AUTHZ-002).
    if not rest or firm_role_allows(ctx, "client.read"):
        return "open"
    team = await _clients_on_team(ctx)
    return "open" if all(c in team for c in rest) else "locked"


async def _engagement_client(ctx: AuthContext, row: SessionRow) -> frozenset[UUID]:
    """The session's engagement's client, which a person who may read the session reads."""
    engagement = ref_of(row.context_refs, "engagement")
    if engagement is None:
        return frozenset()
    try:
        ref = await get_ref(ctx, UUID(engagement))
    except NotFound:
        return frozenset()
    return frozenset({ref.client_id})


async def _readable(ctx: AuthContext, row: SessionRow) -> None:
    """The owner reads their own; anyone else only through the session's engagement."""
    if row.deleted:
        raise NotFound("session")
    if row.owner_user_id == ctx.user_id:
        return
    engagement = ref_of(row.context_refs, "engagement")
    if engagement is None:
        raise NotFound("session")
    ref = await get_ref(ctx, UUID(engagement))  # a wall answers 404
    if not await could(ctx, ctx.user_id, "engagement.read", ref.resource()):
        raise NotFound("session")


@dataclass(frozen=True)
class ItemView:
    id: UUID
    seq: int
    kind: str
    payload: dict[str, object]
    run_id: UUID | None
    step_id: UUID | None
    actor_kind: str
    actor_name: str | None
    created_at: datetime


@dataclass(frozen=True)
class SessionView:
    row: SessionRow
    locked: bool
    items: list[ItemView]
    allowed_actions: list[str]


async def _session_resource(ctx: AuthContext, row: SessionRow) -> Resource:
    """Where a session's actions are decided: its engagement when it has one (engagement roles
    hold `session.*` there), else the firm."""
    engagement = ref_of(row.context_refs, "engagement")
    if engagement is None:
        return Resource.firm(ctx.tenant_id)
    return (await get_ref(ctx, UUID(engagement))).resource()  # a wall answers 404


async def get_session(ctx: AuthContext, session_id: UUID) -> SessionView:
    async with tenant_session(ctx.tenant) as session:
        row = await load_session(session, session_id)
        if row is None:
            raise NotFound("session")
        await _readable(ctx, row)
        await authorise(ctx, "session.read", await _session_resource(ctx, row))
        access = await viewer_access(ctx, row.client_scope, await _engagement_client(ctx, row))
        if access == "omitted":
            raise NotFound("session")
        raw: Sequence[Any] = (  # Any: SQL rows
            []
            if access == "locked"
            else (await session.execute(_ITEMS, {"id": session_id, "page": ITEMS_PAGE})).all()
        )
    names = await display_names([row.owner_user_id])
    owner = names.get(row.owner_user_id)
    items = [
        ItemView(
            id=r.id,
            seq=int(r.seq),
            kind=r.kind,
            payload=cast(dict[str, object], r.payload),
            run_id=r.run_id,
            step_id=r.step_id,
            actor_kind=r.actor_kind,
            # "<person> via Agent" is the client's rendering; the name is the person's (DEC-19)
            actor_name=owner if r.actor_kind in ("human", "agent") else None,
            created_at=r.created_at,
        )
        for r in reversed(raw)
    ]
    mine = row.owner_user_id == ctx.user_id
    allowed = ["message", "manage"] if mine and access == "open" else (["manage"] if mine else [])
    return SessionView(row, access == "locked", items, allowed)


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@dataclass(frozen=True)
class Posted:
    item_id: UUID
    seq: int
    run_id: UUID | None


_BY_KEY = text(
    "SELECT id, seq, run_id FROM session_items WHERE session_id = :id AND kind = :kind "
    "AND payload->>'key' = :key LIMIT 1"
)
_LOCK = text(
    "SELECT item_seq, state FROM workbench_sessions WHERE id = :id AND deleted_at IS NULL "
    "FOR UPDATE"
)
_ITEM = text(
    "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, run_id, step_id, "
    "actor_kind, actor_id, classification) VALUES (:t, :s, :seq, :kind, CAST(:payload AS jsonb), "
    ":run, :step, :actor_kind, :actor, :class) RETURNING id"
)
_BUMP = text(
    "UPDATE workbench_sessions SET item_seq = :seq, last_item_at = clock_timestamp(), "
    "state = coalesce(:state, state) WHERE id = :id"
)


async def capability_of(tenant: TenantContext, row: SessionRow) -> str | None:
    named = ref_of(row.context_refs, "capability")
    if named is not None:
        return named
    return SYNTHETIC_DEFAULT if await is_synthetic_firm(tenant) else None


async def post_message(
    ctx: AuthContext,
    session_id: UUID,
    body: str,
    idempotency_key: str,
    answers_seq: int | None = None,
) -> Posted:
    if not await flag_enabled(ctx.tenant, AGENT_RUNTIME_V2):
        raise NotFound(AGENT_RUNTIME_V2.name)
    kind = "answer" if answers_seq is not None else "user_message"
    key = key_hash(idempotency_key)
    async with tenant_session(ctx.tenant) as session:
        row = await load_session(session, session_id)
        if row is None or row.deleted:
            raise NotFound("session")
        await authorise(ctx, "session.create", await _session_resource(ctx, row))
        if row.owner_user_id != ctx.user_id:
            raise Forbidden("session.create", "attribute")  # only the owner posts
        again = (
            await session.execute(_BY_KEY, {"id": session_id, "kind": kind, "key": key})
        ).first()
        if again is not None:
            return Posted(again.id, int(again.seq), again.run_id)
        if answers_seq is not None:
            asked = await session.scalar(
                text(
                    "SELECT 1 FROM session_items WHERE session_id = :id AND seq = :seq "
                    "AND kind = 'question'"
                ),
                {"id": session_id, "seq": answers_seq},
            )
            if asked is None:
                raise NotFound("session_question")
    if await viewer_access(ctx, row.client_scope, await _engagement_client(ctx, row)) != "open":
        raise SessionLocked
    engagement = ref_of(row.context_refs, "engagement")
    capability = await capability_of(ctx.tenant, row)
    run_id: UUID | None = None
    blocked: str | None = None
    if engagement is not None and capability is not None:
        # T-04-T37 (DF-04): consent, boundary and pause facts first; no run, no model call.
        ready, blocked = await capability_ready(ctx, UUID(engagement), capability)
        if ready:
            blocked = None
    if engagement is not None and capability is not None and blocked is None:
        run_id = await open_turn_run(
            ctx,
            agent_id=capability,
            engagement_id=UUID(engagement),
            session_id=session_id,
            inputs={"session_id": str(session_id), "kind": kind},
        )
    payload: dict[str, object] = {"v": 1, "body": body, "key": key}
    if blocked is not None:
        payload["blocked"] = blocked
    if answers_seq is not None:
        payload["answers_seq"] = answers_seq
    async with uow(ctx.tenant) as tx:
        locked = (await tx.session.execute(_LOCK, {"id": session_id})).first()
        if locked is None:
            raise NotFound("session")
        seq = int(locked.item_seq) + 1
        item_id = cast(
            UUID,
            await tx.session.scalar(
                _ITEM,
                {
                    "t": ctx.tenant_id,
                    "s": session_id,
                    "seq": seq,
                    "kind": kind,
                    "payload": json.dumps(payload),
                    "run": run_id,
                    "step": None,
                    "actor_kind": "human",
                    "actor": str(ctx.user_id),
                    "class": "restricted",
                },
            ),
        )
        await tx.session.execute(_BUMP, {"seq": seq, "state": "running", "id": session_id})
        tx.record(
            "session.message_posted",
            target=Target("workbench_session", session_id),
            after=Ref(seq=seq),
        )
    signal = "answer" if answers_seq is not None else "user_message"
    await signal_with_start(
        WorkbenchSessionWorkflow,
        SessionInput(str(ctx.tenant_id), str(session_id)),
        id=session_workflow_id(str(ctx.tenant_id), str(session_id)),
        signal=signal,
        payload=seq if answers_seq is None else [seq, answers_seq],
    )
    return Posted(item_id, seq, run_id)


async def open_session(
    ctx: AuthContext,
    *,
    title: str,
    origin: str,
    engagement_id: UUID | None = None,
    capability: str | None = None,
    subject: tuple[str, UUID] | None = None,
) -> UUID:
    """A session for `ctx` (module docstring); its engagement must be readable. `subject` binds it
    to one record (T-04-T37: `("tax_return", id)`), which its owner checked the person may read."""
    refs: list[dict[str, str]] = []
    clients: list[UUID] = []
    if engagement_id is None:
        await authorise(ctx, "session.create", Resource.firm(ctx.tenant_id))
    else:
        ref = await get_ref(ctx, engagement_id)
        await authorise(ctx, "session.create", ref.resource())
        await authorise(ctx, "engagement.read", ref.resource())
        refs.append({"kind": "engagement", "id": str(engagement_id)})
        clients.append(ref.client_id)
    if capability is not None:
        refs.append({"kind": "capability", "id": capability})
    if subject is not None:
        refs.append({"kind": subject[0], "id": str(subject[1])})
    async with uow(ctx.tenant) as tx:
        session_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO workbench_sessions (tenant_id, title, owner_user_id, origin, "
                    "context_refs, client_scope) VALUES (:t, :title, :me, :origin, "
                    "CAST(:refs AS jsonb), :clients) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "title": title,
                    "me": ctx.user_id,
                    "origin": origin,
                    "refs": json.dumps(refs),
                    "clients": clients,
                },
            ),
        )
        tx.record(
            "session.created",
            target=Target("workbench_session", session_id),
            after=Ref(owner=ctx.user_id),
        )
    return session_id


@dataclass(frozen=True)
class SessionSummary:
    id: UUID
    title: str
    state: str
    last_item_at: datetime | None


async def _owned_subject_sessions(
    ctx: AuthContext, kind: str, subject_id: UUID
) -> list[SessionSummary]:
    """The person's own sessions bound to one record, newest first (TAX-08 History). The owner of
    the record has checked the person may read it; callers go through `subject_sessions`, which
    authorises `session.read` on the record's engagement."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, title, state, last_item_at FROM workbench_sessions "
                    "WHERE owner_user_id = :me AND deleted_at IS NULL AND context_refs @> "
                    "CAST(:ref AS jsonb) ORDER BY coalesce(last_item_at, created_at) DESC LIMIT 50"
                ),
                {"me": ctx.user_id, "ref": json.dumps([{"kind": kind, "id": str(subject_id)}])},
            )
        ).all()
    return [SessionSummary(r.id, r.title, r.state, r.last_item_at) for r in rows]


async def open_subject_session(ctx: AuthContext, kind: str, subject_id: UUID, title: str) -> UUID:
    """A session bound to one record (T-04-T37): its owner authorises the person and names the
    capability. Availability is read first; an unavailable one opens nothing (no model call)."""
    engagement, capability = await subject_engagement(ctx, kind, subject_id)
    ready, reason = await capability_ready(ctx, engagement, capability)
    if not ready:
        raise CapabilityUnavailable(facts={"reason": reason or "capability_unavailable"})
    return await open_session(
        ctx,
        title=title,
        origin="manual",
        engagement_id=engagement,
        capability=capability,
        subject=(kind, subject_id),
    )


async def subject_sessions(ctx: AuthContext, kind: str, subject_id: UUID) -> list[SessionSummary]:
    engagement, _ = await subject_engagement(ctx, kind, subject_id)  # the record is readable
    ref = await get_ref(ctx, engagement)
    await authorise(ctx, "session.read", ref.resource())
    return await _owned_subject_sessions(ctx, kind, subject_id)
