"""To-dos (P-05-T06; SPEC-650 §3.6 to 3.8; DEC-3203). Built dark behind `collaboration.v2`.

- **People only.** The assignee is a member of the engagement who may read its to-dos (walls,
  independence): never the agent, which is not a person (422 `assignee_not_allowed`). Every
  action denies the agent by the matrix (INV-1). A to-do is never a gate: it never enters the
  human-gate projection and never blocks a sign-off (R7, C13).
- **Scopes.** An engagement to-do goes by the engagement (`visible()`, `authorise`); a firm-scope
  to-do (J27's "Update skill BH-SK-410") is read and changed only by its creator and its
  assignee, its actions decided on the firm resource (partner- and manager-level people).
- **Autosave** under `If-Match: <version>` (409 `stale_version`; there is no Save button).
  Complete and Reopen (= Undo, DEC-24) move `open` and `done`; Overdue is derived at read time
  in the firm's zone and never stored. Delete is soft (creator, assignee or manager-or-above).
- **Checklist** of at most 8 items (422 `checklist_full`), each change audited.
- **Anchor.** A to-do may sit on any registered anchor of its engagement and is itself the anchor
  `todo` (its threads, SHL-17's comment count). The anchor row's text is sealed as a snapshot.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func

from abacus.kernel import clock
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.collaboration import repository as repo
from abacus.modules.collaboration.anchors import (
    AnchorFacts,
    AnchorScopeMismatch,
    Locator,
    anchor_facts,
)
from abacus.modules.collaboration.candidates import assignable
from abacus.modules.collaboration.errors import (
    AssigneeNotAllowed,
    ChecklistFull,
    IfMatchRequired,
    StaleVersion,
    TodoAlreadyDone,
    TodoNotDone,
)
from abacus.modules.collaboration.events import (
    TodoAssigned,
    TodoCompleted,
    TodoCreated,
    TodoDeleted,
    TodoMoved,
    TodoReopened,
    TodoUpdated,
)
from abacus.modules.collaboration.models import Todo, TodoChecklistItem
from abacus.modules.engagements.api import engagement_label, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    could,
    engagement_role_of,
    firm_time_zone,
)

MAX_CHECKLIST: Final = 8
TODO_ACTIONS: Final = (
    "todo.update",
    "todo.complete",
    "todo.assign",
    "todo.delete",
    "comment.create",
)
# Manager-or-above may delete anyone's to-do on the engagement (AC-26).
DELETERS: Final = frozenset({"engagement_partner", "manager"})


class EngagementRequired(DomainInvalid):
    code = "engagement_required"


class NotYoursToDelete(DomainForbidden):
    """AC-26: only the creator, the assignee or a manager-or-above deletes."""

    code = "todo_delete_not_allowed"


@dataclass(frozen=True)
class ChecklistView:
    id: UUID
    position: int
    text: str
    done: bool
    done_by: UUID | None
    done_at: datetime | None


@dataclass(frozen=True)
class TodoView:
    id: UUID
    scope_kind: str
    engagement_id: UUID | None
    title: str
    status: str
    overdue: bool
    bucket: str | None
    assignee: UUID
    created_by: UUID
    created_at: datetime
    due_on: date | None
    anchor_kind: str | None
    anchor_id: UUID | None
    locator: dict[str, str | int] | None
    anchor: AnchorFacts | None
    row_text: str | None
    source_thread_id: UUID | None
    done_by: UUID | None
    done_at: datetime | None
    unread: bool
    checklist: list[ChecklistView]
    comment_count: int
    version: int
    allowed_actions: list[str] = field(default_factory=list[str])


# --- the `todo` anchor ---------------------------------------------------------------------------


class TodoAnchors:
    """A to-do as an anchor (P-05 §4.1): its threads and the C-27 chips; no locator; `follow`."""

    locator_keys: frozenset[str] = frozenset()

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        del locator
        async with tenant_session(ctx.tenant) as session:
            todo = await repo.get_todo(session, anchor_id)
        if todo is None:
            return None
        if todo.engagement_id is None:
            if ctx.user_id not in (todo.created_by, todo.assignee_user_id):
                return None
            return AnchorFacts(ctx.tenant_id, None, None, "To-do")
        ref = await get_ref(ctx, todo.engagement_id)
        label = await engagement_label(ctx.tenant, ref.id)
        client = label.client_name if label is not None else ""
        return AnchorFacts(
            ctx.tenant_id,
            ref.id,
            ref.client_id,
            f"{client} · {todo.title}" if client else todo.title,
            archived=ref.archived,
            work_item_id=todo.work_item_id,
        )


TODO_ANCHORS: Final = TodoAnchors()


# --- access --------------------------------------------------------------------------------------


async def _resource(ctx: AuthContext, todo: Todo) -> Resource:
    if todo.engagement_id is None:
        return Resource.firm(ctx.tenant_id)
    return (await get_ref(ctx, todo.engagement_id)).resource()


async def _todo(ctx: AuthContext, todo_id: UUID, action: str) -> tuple[Todo, Resource]:
    """The live to-do once `action` is allowed on it; 404 for a firm-scope to-do that is not
    the caller's (AC-28) and for a soft-deleted one."""
    async with tenant_session(ctx.tenant) as session:
        todo = await repo.get_todo(session, todo_id)
    if todo is None or ctx.client:
        raise NotFound("todo")
    if todo.engagement_id is None and ctx.user_id not in (todo.created_by, todo.assignee_user_id):
        raise NotFound("todo")
    resource = await _resource(ctx, todo)
    await authorise(ctx, action, resource)
    return todo, resource


async def _today(ctx: AuthContext) -> date:
    zone = await firm_time_zone(ctx.tenant)
    try:
        return await clock.today(ctx.tenant, zone=ZoneInfo(zone))
    except (KeyError, ValueError):
        return await clock.today(ctx.tenant)


def _event_fields(todo: Todo) -> dict[str, object]:
    return {
        "todo_id": todo.id,
        "scope_kind": todo.scope_kind,
        "engagement_id": todo.engagement_id,
        "anchor_kind": todo.anchor_kind,
        "anchor_id": todo.anchor_id,
        "assignee_user_id": todo.assignee_user_id,
    }


async def _check_assignee(ctx: AuthContext, engagement_id: UUID | None, user_id: UUID) -> None:
    """AC-19: a human member of the engagement who may read its to-dos; for a firm-scope to-do,
    a firm member who may hold firm-scope to-dos."""
    if engagement_id is None:
        if user_id == ctx.user_id or await could(
            ctx, user_id, "todo.read", Resource.firm(ctx.tenant_id)
        ):
            return
        raise AssigneeNotAllowed
    if not await assignable(ctx, await get_ref(ctx, engagement_id), user_id):
        raise AssigneeNotAllowed


# --- writes --------------------------------------------------------------------------------------


async def create(
    ctx: AuthContext,
    *,
    scope_kind: str,
    engagement_id: UUID | None,
    title: str,
    assignee_user_id: UUID,
    due_on: date | None,
    anchor: tuple[str, UUID, Locator | None] | None,
    checklist: Sequence[str],
    source_thread_id: UUID | None,
) -> UUID:
    """AC-17, AC-18, AC-19, AC-14 (a to-do made from a thread records `converted` on it)."""
    if ctx.client:
        raise NotFound("todo")
    if scope_kind == "engagement":
        if engagement_id is None:
            raise EngagementRequired
        ref = await get_ref(ctx, engagement_id)
        await authorise(ctx, "todo.create", ref.resource())
        client_id: UUID | None = ref.client_id
    else:
        if engagement_id is not None or anchor is not None or source_thread_id is not None:
            raise AnchorScopeMismatch  # a firm-scope to-do sits on nothing of an engagement
        await authorise(ctx, "todo.create", Resource.firm(ctx.tenant_id))
        client_id = None
    await _check_assignee(ctx, engagement_id, assignee_user_id)
    facts: AnchorFacts | None = None
    if anchor is not None:
        facts = await anchor_facts(ctx, anchor[0], anchor[1], anchor[2])
        if facts is None:
            raise NotFound("anchor")
        if facts.engagement_id != engagement_id:
            raise AnchorScopeMismatch
        await authorise(ctx, "todo.read", facts.resource())
    thread = None
    if source_thread_id is not None:
        async with tenant_session(ctx.tenant) as session:
            thread = await repo.get_thread(session, source_thread_id)
        if thread is None or thread.engagement_id != engagement_id:
            raise NotFound("comment_thread")
    row_sealed: bytes | None = None
    row_fingerprint: str | None = None
    if facts is not None and facts.row_text:
        row_fingerprint = hashlib.sha256(facts.row_text.encode()).hexdigest()
        row_sealed = await seal(ctx.tenant_id, facts.row_text.encode(), row_fingerprint)
    texts = [t.strip() for t in checklist if t.strip()]
    if len(texts) > MAX_CHECKLIST:
        raise ChecklistFull
    async with uow(ctx.tenant) as tx:
        todo_id = await repo.insert_todo(
            tx.session,
            tenant_id=ctx.tenant_id,
            scope_kind=scope_kind,
            engagement_id=engagement_id,
            work_item_id=facts.work_item_id if facts is not None else None,
            client_id=client_id,
            title=title.strip(),
            assignee_user_id=assignee_user_id,
            due_on=due_on,
            anchor_kind=anchor[0] if anchor is not None else None,
            anchor_id=anchor[1] if anchor is not None else None,
            anchor_locator=dict(anchor[2]) if anchor is not None and anchor[2] else None,
            row_text_sealed=row_sealed,
            row_text_fingerprint=row_fingerprint,
            source_thread_id=source_thread_id,
            created_by=ctx.user_id,
        )
        await repo.insert_checklist_items(
            tx.session, ctx.tenant_id, todo_id, list(enumerate(texts, start=1))
        )
        refs: dict[str, UUID | int | str] = {"scope": scope_kind, "checklist": len(texts)}
        if anchor is not None:
            refs.update(anchor_kind=anchor[0], anchor_id=anchor[1])
        tx.record("todo.created", target=Target("todo", todo_id), after=Ref(**refs))
        tx.record(
            "todo.assigned",
            target=Target("todo", todo_id),
            after=Ref(assignee=assignee_user_id),
        )
        fields = {
            "todo_id": todo_id,
            "scope_kind": scope_kind,
            "engagement_id": engagement_id,
            "anchor_kind": anchor[0] if anchor is not None else None,
            "anchor_id": anchor[1] if anchor is not None else None,
            "assignee_user_id": assignee_user_id,
        }
        tx.emit(TodoCreated.model_validate(fields))
        if assignee_user_id != ctx.user_id:
            tx.emit(
                TodoAssigned(
                    todo_id=todo_id,
                    assignee_user_id=assignee_user_id,
                    assigned_by=ctx.user_id,
                    engagement_id=engagement_id,
                )
            )
        if thread is not None:
            await repo.insert_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=thread.engagement_id,
                thread_id=thread.id,
                kind="converted",
                actor_user_id=ctx.user_id,
                ref_type="todo",
                ref_id=todo_id,
            )
            tx.record(
                "comment_thread.converted",
                target=Target("comment_thread", thread.id),
                after=Ref(ref_type="todo", ref_id=todo_id),
            )
    return todo_id


def if_match_version(if_match: str | None) -> int:
    if if_match is None:
        raise IfMatchRequired
    try:
        return int(if_match.strip().strip('"').removeprefix("W/").strip('"'))
    except ValueError:
        raise StaleVersion from None


async def _changed(tx: UnitOfWork, todo: Todo | None) -> Todo:
    if todo is None:
        raise StaleVersion
    tx.emit(TodoUpdated.model_validate(_event_fields(todo)))
    return todo


async def patch(
    ctx: AuthContext,
    todo_id: UUID,
    *,
    title: str | None,
    due_on: date | None,
    clear_due_on: bool,
    if_match: str | None,
) -> None:
    """AC-20: autosave of the title and the due date under the version the editor read."""
    expected = if_match_version(if_match)
    await _todo(ctx, todo_id, "todo.update")
    values: dict[str, str | date | None] = {}
    if title is not None:
        values["title"] = title.strip()
    if clear_due_on:
        values["due_on"] = None
    elif due_on is not None:
        values["due_on"] = due_on
    async with uow(ctx.tenant) as tx:
        await _changed(
            tx,
            await repo.update_todo_values(tx.session, todo_id, values, expected_version=expected),
        )
        tx.record(
            "todo.updated",
            target=Target("todo", todo_id),
            after=Ref(fields=",".join(sorted(values)) or "none", version=expected + 1),
        )


async def assign(ctx: AuthContext, todo_id: UUID, assignee_user_id: UUID) -> None:
    """Reassign… (SHL-17c): the new assignee hears of it; the dot is theirs again."""
    todo, _ = await _todo(ctx, todo_id, "todo.assign")
    await _check_assignee(ctx, todo.engagement_id, assignee_user_id)
    async with uow(ctx.tenant) as tx:
        changed = await _changed(
            tx,
            await repo.update_todo(
                tx.session,
                todo_id,
                expected_version=None,
                assignee_user_id=assignee_user_id,
                assignee_seen_at=None,
            ),
        )
        tx.record(
            "todo.assigned", target=Target("todo", todo_id), after=Ref(assignee=assignee_user_id)
        )
        if assignee_user_id != ctx.user_id:
            tx.emit(
                TodoAssigned(
                    todo_id=todo_id,
                    assignee_user_id=assignee_user_id,
                    assigned_by=ctx.user_id,
                    engagement_id=changed.engagement_id,
                )
            )


async def complete(ctx: AuthContext, todo_id: UUID) -> None:
    """AC-24: Mark done (the ring); its Undo is `reopen`."""
    todo, _ = await _todo(ctx, todo_id, "todo.complete")
    if todo.status == "done":
        raise TodoAlreadyDone
    async with uow(ctx.tenant) as tx:
        done = await repo.update_todo(
            tx.session,
            todo_id,
            expected_version=todo.version,
            status="done",
            done_by=ctx.user_id,
            done_at=func.now(),
        )
        if done is None:
            raise StaleVersion
        tx.record("todo.completed", target=Target("todo", todo_id))
        tx.emit(TodoCompleted.model_validate(_event_fields(done)))


async def reopen(ctx: AuthContext, todo_id: UUID) -> None:
    """AC-24, AC-25: Reopen, and the Undo of a completion (a compensating command, DEC-24)."""
    todo, _ = await _todo(ctx, todo_id, "todo.complete")
    if todo.status != "done":
        raise TodoNotDone
    async with uow(ctx.tenant) as tx:
        opened = await repo.update_todo(
            tx.session,
            todo_id,
            expected_version=todo.version,
            status="open",
            done_by=None,
            done_at=None,
        )
        if opened is None:
            raise StaleVersion
        tx.record("todo.reopened", target=Target("todo", todo_id))
        tx.emit(TodoReopened.model_validate(_event_fields(opened)))


async def move(ctx: AuthContext, todo_id: UUID, anchor: tuple[str, UUID, Locator | None]) -> None:
    """AC-27: re-anchor within the same engagement only (422 `anchor_scope_mismatch`)."""
    todo, _ = await _todo(ctx, todo_id, "todo.update")
    if anchor[0] == "todo" and anchor[1] == todo_id:
        raise AnchorScopeMismatch  # never on itself
    facts = await anchor_facts(ctx, anchor[0], anchor[1], anchor[2])
    if facts is None:
        raise NotFound("anchor")
    if todo.engagement_id is None or facts.engagement_id != todo.engagement_id:
        raise AnchorScopeMismatch
    await authorise(ctx, "todo.read", facts.resource())
    async with uow(ctx.tenant) as tx:
        moved = await repo.update_todo(
            tx.session,
            todo_id,
            expected_version=None,
            anchor_kind=anchor[0],
            anchor_id=anchor[1],
            anchor_locator=dict(anchor[2]) if anchor[2] else None,
            work_item_id=facts.work_item_id,
        )
        if moved is None:
            raise NotFound("todo")
        tx.record(
            "todo.moved",
            target=Target("todo", todo_id),
            after=Ref(anchor_kind=anchor[0], anchor_id=anchor[1]),
        )
        tx.emit(TodoMoved.model_validate(_event_fields(moved)))


async def delete(ctx: AuthContext, todo_id: UUID) -> TodoView:
    """AC-26: a soft delete after Delete… (hidden from lists and counts, never hard-deleted)."""
    todo, _ = await _todo(ctx, todo_id, "todo.delete")
    if not await _may_delete(ctx, todo):
        raise NotYoursToDelete
    view = await read(ctx, todo_id, "todo.delete")
    async with uow(ctx.tenant) as tx:
        gone = await repo.update_todo(
            tx.session,
            todo_id,
            expected_version=None,
            deleted_at=func.now(),
            deleted_by=ctx.user_id,
        )
        if gone is None:
            raise NotFound("todo")
        tx.record("todo.deleted", target=Target("todo", todo_id))
        tx.emit(TodoDeleted.model_validate(_event_fields(gone)))
    return view


async def _may_delete(ctx: AuthContext, todo: Todo) -> bool:
    if ctx.user_id in (todo.created_by, todo.assignee_user_id):
        return True
    if todo.engagement_id is None:
        return False
    return await engagement_role_of(ctx.tenant, todo.engagement_id, ctx.user_id) in DELETERS


async def seen(ctx: AuthContext, todo_id: UUID) -> None:
    """AC-21: the assignee opened it; the unread dot clears. Nobody else's open counts."""
    todo, _ = await _todo(ctx, todo_id, "todo.read")
    if todo.assignee_user_id != ctx.user_id or todo.assignee_seen_at is not None:
        return
    async with uow(ctx.tenant) as tx:
        await repo.update_todo(
            tx.session, todo_id, expected_version=None, bump=False, assignee_seen_at=func.now()
        )
        tx.record("todo.seen", target=Target("todo", todo_id))


async def add_item(ctx: AuthContext, todo_id: UUID, text: str) -> None:
    """AC-22: at most 8 items (422 `checklist_full` on a ninth)."""
    await _todo(ctx, todo_id, "todo.update")
    async with uow(ctx.tenant) as tx:
        count = await repo.checklist_count(tx.session, todo_id)
        if count >= MAX_CHECKLIST:
            raise ChecklistFull
        await repo.insert_checklist_items(
            tx.session, ctx.tenant_id, todo_id, [(count + 1, text.strip())]
        )
        tx.record(
            "todo.checklist_changed",
            target=Target("todo", todo_id),
            after=Ref(change="added", position=count + 1),
        )


async def change_item(
    ctx: AuthContext, todo_id: UUID, item_id: UUID, *, text: str | None, done: bool | None
) -> None:
    """Toggle (checked, unchecked) or edit an item; each change audited."""
    await _todo(ctx, todo_id, "todo.update")
    async with uow(ctx.tenant) as tx:
        item = await repo.get_checklist_item(tx.session, todo_id, item_id)
        if item is None:
            raise NotFound("todo_checklist_item")
        await repo.set_checklist_item(
            tx.session, item_id, text=text.strip() if text else None, done=done, by=ctx.user_id
        )
        change = "edited" if done is None else ("checked" if done else "unchecked")
        tx.record(
            "todo.checklist_changed",
            target=Target("todo", todo_id),
            after=Ref(change=change, position=item.position),
        )


async def remove_item(ctx: AuthContext, todo_id: UUID, item_id: UUID) -> None:
    await _todo(ctx, todo_id, "todo.update")
    async with uow(ctx.tenant) as tx:
        if not await repo.remove_checklist_item(tx.session, todo_id, item_id):
            raise NotFound("todo_checklist_item")
        tx.record(
            "todo.checklist_changed", target=Target("todo", todo_id), after=Ref(change="removed")
        )


# --- reads ---------------------------------------------------------------------------------------


async def _views(ctx: AuthContext, todos: Sequence[Todo]) -> list[TodoView]:
    if not todos:
        return []
    today = await _today(ctx)
    ids = [t.id for t in todos]
    async with tenant_session(ctx.tenant) as session:
        items = await repo.list_checklist(session, ctx, ids)
        comments = dict(await repo.comment_counts_on(session, ctx, "todo", ids))
    by_todo: dict[UUID, list[TodoChecklistItem]] = {}
    for item in items:
        by_todo.setdefault(item.todo_id, []).append(item)
    views: list[TodoView] = []
    resources: dict[UUID | None, Resource] = {}
    for t in todos:
        if t.engagement_id not in resources:
            resources[t.engagement_id] = await _resource(ctx, t)
        allowed = await allowed_actions(ctx, resources[t.engagement_id], TODO_ACTIONS)
        actions = [a for a in TODO_ACTIONS if a in allowed]
        if "todo.delete" in actions and not await _may_delete(ctx, t):
            actions.remove("todo.delete")
        if t.engagement_id is None and "comment.create" in actions:
            actions.remove("comment.create")  # a thread needs an engagement
        facts = None
        if t.anchor_kind is not None and t.anchor_id is not None:
            try:
                facts = await anchor_facts(ctx, t.anchor_kind, t.anchor_id, t.anchor_locator)
            except NotFound:
                facts = None
        row_text = None
        if t.row_text_sealed is not None and t.row_text_fingerprint is not None:
            row_text = (
                await open_sealed(ctx.tenant_id, t.row_text_sealed, t.row_text_fingerprint)
            ).decode()
        bucket = repo.bucket_of(t.due_on, today) if t.status == "open" else None
        views.append(
            TodoView(
                t.id,
                t.scope_kind,
                t.engagement_id,
                t.title,
                t.status,
                bucket == "overdue",
                bucket,
                t.assignee_user_id,
                t.created_by,
                t.created_at,
                t.due_on,
                t.anchor_kind,
                t.anchor_id,
                t.anchor_locator,
                facts,
                row_text,
                t.source_thread_id,
                t.done_by,
                t.done_at,
                t.assignee_user_id == ctx.user_id
                and t.created_by != ctx.user_id
                and t.assignee_seen_at is None,
                [
                    ChecklistView(i.id, i.position, i.text, i.done, i.done_by, i.done_at)
                    for i in by_todo.get(t.id, [])
                ],
                comments.get(t.id, 0),
                t.version,
                actions,
            )
        )
    return views


async def read(ctx: AuthContext, todo_id: UUID, action: str = "todo.read") -> TodoView:
    todo, _ = await _todo(ctx, todo_id, action)
    return (await _views(ctx, [todo]))[0]


@dataclass(frozen=True)
class Page:
    items: list[TodoView]
    counts: dict[str, int]


async def mine(ctx: AuthContext, *, status: str | None) -> Page:
    """AC-29 (HOME-01i reads the same): the caller's to-dos with the bands of the open ones."""
    if ctx.client:
        raise NotFound("todo")
    async with tenant_session(ctx.tenant) as session:
        open_rows = await repo.list_my_todos(session, ctx, status="open")
        done_count = len(await repo.list_my_todos(session, ctx, status="done"))
        rows = (
            open_rows
            if status == "open"
            else await repo.list_my_todos(session, ctx, status=status)
        )
    today = await _today(ctx)
    counts: dict[str, int] = {b: 0 for b in ("overdue", "today", "this_week", "later", "no_date")}
    for t in open_rows:
        counts[repo.bucket_of(t.due_on, today)] += 1
    counts["open"] = len(open_rows)
    counts["done"] = done_count
    return Page(await _views(ctx, rows), counts)


async def on_anchor(ctx: AuthContext, kind: str, anchor_id: UUID) -> list[TodoView]:
    facts = await anchor_facts(ctx, kind, anchor_id, None)
    if facts is None or ctx.client:
        raise NotFound("anchor")
    await authorise(ctx, "todo.read", facts.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.list_todos_on(session, ctx, anchor_kind=kind, anchor_id=anchor_id)
    return await _views(ctx, rows)


async def anchor_counts(
    ctx: AuthContext, anchors: Sequence[tuple[str, UUID, Locator | None]]
) -> list[tuple[str, UUID, Locator | None, int]]:
    """The "n To-do" chips: open to-dos per anchor the caller may read (others count 0)."""
    readable: set[tuple[str, UUID]] = set()
    for kind, anchor_id, locator in anchors:
        facts = await anchor_facts(ctx, kind, anchor_id, locator)
        if facts is None or ctx.client:
            continue
        resource = facts.resource()
        if facts.engagement_id is None or "todo.read" in await allowed_actions(
            ctx, resource, ("todo.read",)
        ):
            readable.add((kind, anchor_id))
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.list_todos_on_anchors(session, ctx, sorted(readable, key=str))
    found: list[tuple[str, UUID, Locator | None, int]] = []
    for kind, anchor_id, locator in anchors:
        n = sum(r.anchor_kind == kind and r.anchor_id == anchor_id for r in rows)
        found.append((kind, anchor_id, locator, n if (kind, anchor_id) in readable else 0))
    return found
