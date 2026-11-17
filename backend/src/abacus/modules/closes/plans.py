"""The close plan (C-01-T15; TASK-8033; SPEC-655 AC-14 to AC-22; CLS-09).

- **One plan per client entity.** `/clients/{client_id}/close-plan` resolves to the entity of the
  client's newest open Monthly close engagement, which is also the resource every plan action
  authorises on (the matrix grants are engagement roles; DEC-5021).
- **Versions.** A draft is copied from a version (rows and request templates); one draft per plan
  (the partial unique index; 409 `draft_exists`). Rows and request templates change only while
  their version is a draft (trigger `close_plan_child_frozen`), each edit under If-Match on the
  version's row version (409 `stale_version` naming the person who drafted it).
- **Publish** (AC-17, AC-22): a Manager or Partner, a live human, with `effective_from`; the
  trigger refuses a version holding a drafted row nobody adopted (409 `unadopted_rows`). Before
  the version publishes, every close of the entity past BD1 and not yet pinned is pinned to the
  version it already reads, so a publication never changes a close in progress (QC-2, AC-18).
- **Request publish** (AC-16, QC-8): a Senior's ask raises one HOME-02 gate for the engagement's
  Managers and Partners (`gate_sources.py`) and publishes nothing.
- **History** (AC-15): "<person> via Agent · Close Planner" for an agent-drafted version.
- **Templates** (AC-20): industry templates are DB content imported through
  `POST /v1/close-templates:import`; nothing is committed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import today
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.closes.contract import (
    AdoptOut,
    CloseAction,
    ClosePersonOut,
    CloseTemplateImportIn,
    CloseTemplateOut,
    CloseTemplatesOut,
    PlanDraftIn,
    PlanHistoryItemOut,
    PlanHistoryOut,
    PlanRowIn,
    PlanRowOut,
    PlanRowPatchIn,
    PlanTallyOut,
    PlanVersionOut,
    PublishIn,
    RequestTemplateIn,
    RequestTemplateOut,
    ThresholdRefOut,
    UnadoptedRows,
)
from abacus.modules.closes.events import ClosePlanPublished, ClosePlanPublishRequested
from abacus.modules.closes.service import StaleClose
from abacus.modules.engagements.api import (
    EngagementRef,
    engagement_type_of,
    engagements_of_client,
    get_ref,
)
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of

type _Row = Row[Any]  # Any: a raw text() row of close_plan_versions or close_plan_rows

READ: Final = "close_plan.read"
EDIT: Final = "close_plan.edit"
DRAFT_FROM_HISTORY: Final = "close_plan.draft_from_history"
PUBLISH: Final = "close_plan.publish"
REQUEST: Final = "close_plan.request_publish"
ADOPT: Final = "suggestion.resolve"
IMPORT: Final = "close_template.import"
PLANNER: Final = "Close Planner"
_IS_PROCEDURES: Final = frozenset({"recategorize", "flux"})


class DraftExists(DomainConflict):
    """A plan holds one draft at a time (CLS-09 b)."""

    code = "draft_exists"


class VersionNotDraft(DomainConflict):
    """Only a draft is edited or published; a published version is immutable (AC-17)."""

    code = "plan_version_frozen"


class TemplateExists(DomainConflict):
    code = "template_exists"


# --- scope ---------------------------------------------------------------------------------------


async def _scope(ctx: AuthContext, client_id: UUID, action: str) -> EngagementRef:
    """The client's newest open Monthly close engagement, authorised for `action`. A client with
    none (or one the person may not see) is 404: a plan is never revealed (INV-3)."""
    for engagement_id in await engagements_of_client(ctx.tenant, client_id):
        if await engagement_type_of(ctx.tenant, engagement_id) != "cas_monthly_close":
            continue
        ref = await get_ref(ctx, engagement_id)
        if ref.archived:
            continue
        try:
            await authorise(ctx, action, ref.resource())
        except NotFound:
            raise NotFound("close_plan") from None
        return ref
    raise NotFound("close_plan")


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


def _seen(if_match: str) -> int:
    raw = if_match.strip().removeprefix("W/").strip('"')
    try:
        return int(raw)
    except ValueError:
        raise StaleClose(facts={"if_match": "not a version"}) from None


# --- reads ---------------------------------------------------------------------------------------

_PLAN = text("SELECT id FROM close_plans WHERE client_entity_id = :e")
_VERSIONS = text(
    "SELECT id, version, status, effective_from, change_note, drafted_by, drafted_by_run_id, "
    "publish_requested_by, publish_requested_at, published_by, published_at, row_version, "
    "created_at FROM close_plan_versions WHERE plan_id = :p ORDER BY version"
)
_ROWS = text(
    "SELECT id, position, account_external_id, account_name, account_class, procedure, method, "
    "evidence_required, source, review_level, frequency, threshold_ref, drafted_suggestion_id, "
    "adopted_at FROM close_plan_rows WHERE version_id = :v ORDER BY position, id"
)
_TEMPLATES = text(
    "SELECT id, title, category_path, due_business_day, client_visible "
    "FROM close_request_templates WHERE version_id = :v ORDER BY title, id"
)


async def _plan_id(session: AsyncSession, entity: UUID) -> UUID | None:
    return cast(UUID | None, await session.scalar(_PLAN, {"e": entity}))


async def _versions(session: AsyncSession, plan_id: UUID) -> list[_Row]:
    return list((await session.execute(_VERSIONS, {"p": plan_id})).all())


def _row_out(
    r: _Row,
    previous: dict[str, tuple[object, ...]] | None,
) -> PlanRowOut:
    threshold = r.threshold_ref or None
    if isinstance(threshold, str):
        threshold = json.loads(threshold)
    signature = (r.procedure, r.method, r.evidence_required, r.source, r.review_level, r.frequency)
    key = f"{r.account_external_id}:{r.account_name}:{r.procedure}"
    return PlanRowOut(
        row_id=r.id,
        position=r.position,
        account_external_id=r.account_external_id,
        account_name=r.account_name,
        account_class=r.account_class,
        procedure=r.procedure,
        method=r.method,
        evidence_required=r.evidence_required,
        source=r.source,
        review_level=r.review_level,
        frequency=r.frequency,
        threshold=(
            ThresholdRefOut(
                policy_version_id=UUID(str(threshold["policy_version_id"])),
                label=str(threshold.get("label", "")),
            )
            if threshold and threshold.get("policy_version_id")
            else None
        ),
        drafted=r.drafted_suggestion_id is not None and r.adopted_at is None,
        adopted=r.drafted_suggestion_id is None or r.adopted_at is not None,
        changed_from_previous=previous is not None and previous.get(key) != signature,
    )


def _signatures(
    rows: Sequence[_Row],
) -> dict[str, tuple[object, ...]]:
    return {
        f"{r.account_external_id}:{r.account_name}:{r.procedure}": (
            r.procedure,
            r.method,
            r.evidence_required,
            r.source,
            r.review_level,
            r.frequency,
        )
        for r in rows
    }


async def _version_out(
    ctx: AuthContext,
    session: AsyncSession,
    plan_id: UUID,
    v: _Row,
    prior: _Row | None,
) -> PlanVersionOut:
    rows = list((await session.execute(_ROWS, {"v": v.id})).all())
    previous = None
    if prior is not None and v.status == "draft":
        previous = _signatures(list((await session.execute(_ROWS, {"v": prior.id})).all()))
    templates = list((await session.execute(_TEMPLATES, {"v": v.id})).all())
    names = await names_of([u for u in (v.drafted_by, v.published_by) if u is not None])
    drafter = names.get(v.drafted_by, "")
    publisher = (
        ClosePersonOut(
            user_id=v.published_by,
            name=names.get(v.published_by, ""),
            initials=_initials(names.get(v.published_by, "")),
        )
        if v.published_by is not None
        else None
    )
    out_rows = [_row_out(r, previous) for r in rows]
    manager = sum(r.review_level == "manager_approval" for r in out_rows)
    allowed: list[CloseAction] = []
    if v.status == "draft":
        allowed.append("close_plan.edit")
    return PlanVersionOut(
        plan_id=plan_id,
        version=v.version,
        status=v.status,
        effective_from=v.effective_from,
        change_note=v.change_note,
        drafted_by=f"{drafter} via Agent · {PLANNER}" if v.drafted_by_run_id else drafter,
        published_by=publisher,
        published_at=v.published_at,
        publish_requested=v.publish_requested_at is not None,
        rows=out_rows,
        request_templates=[
            RequestTemplateOut(
                template_id=t.id,
                title=t.title,
                category_path=list(t.category_path or []),
                due_business_day=t.due_business_day,
                client_visible=t.client_visible,
            )
            for t in templates
        ],
        tally=PlanTallyOut(
            procedures=len(out_rows),
            manager=manager,
            senior=len(out_rows) - manager,
            requests_per_month=sum(t.client_visible for t in templates),
        ),
        allowed_actions=allowed,
        row_version=v.row_version,
    )


def _initials(name: str) -> str:
    parts = name.split()
    return ("".join(p[0] for p in (parts[0], parts[-1])) if len(parts) > 1 else name[:2]).upper()


async def get_plan(ctx: AuthContext, client_id: UUID, version: int | None) -> PlanVersionOut:
    """CLS-09: the newest published version (or the one asked for); a plan with no published
    version yet reads its draft (CLS-09 c, d)."""
    ref = await _scope(ctx, client_id, READ)
    async with tenant_session(ctx.tenant) as session:
        plan_id = await _plan_id(session, ref.client_entity_id)
        if plan_id is None:
            raise NotFound("close_plan")
        versions = await _versions(session, plan_id)
        if version is not None:
            chosen = next((v for v in versions if v.version == version), None)
        else:
            published = [v for v in versions if v.status == "published"]
            drafts = [v for v in versions if v.status == "draft"]
            chosen = (published or drafts or [None])[-1]
        if chosen is None:
            raise NotFound("close_plan_version")
        prior = next(
            (
                v
                for v in reversed(versions)
                if v.version < chosen.version and v.status == "published"
            ),
            None,
        )
        out = await _version_out(ctx, session, plan_id, chosen, prior)
    return await _with_actions(ctx, ref, out)


async def _with_actions(
    ctx: AuthContext, ref: EngagementRef, out: PlanVersionOut
) -> PlanVersionOut:
    if out.status != "draft":
        return out
    actions: list[CloseAction] = []
    for action in (EDIT, REQUEST, PUBLISH):
        try:
            await authorise(ctx, action, ref.resource())
            actions.append(cast(CloseAction, action))
        except Forbidden:
            continue
    return out.model_copy(update={"allowed_actions": actions})


async def plan_history(ctx: AuthContext, client_id: UUID) -> PlanHistoryOut:
    ref = await _scope(ctx, client_id, READ)
    async with tenant_session(ctx.tenant) as session:
        plan_id = await _plan_id(session, ref.client_entity_id)
        versions = await _versions(session, plan_id) if plan_id is not None else []
    names = await names_of(
        sorted({u for v in versions for u in (v.drafted_by, v.published_by) if u}, key=str)
    )
    items: list[PlanHistoryItemOut] = []
    for v in reversed(versions):
        if v.status == "published":
            who = names.get(v.published_by, "")
            items.append(
                PlanHistoryItemOut(
                    version=v.version,
                    status="published",
                    attribution=f"v{v.version} published · {who}",
                    at=v.published_at,
                )
            )
        drafter = names.get(v.drafted_by, "")
        by = f"{drafter} via Agent · {PLANNER}" if v.drafted_by_run_id else drafter
        items.append(
            PlanHistoryItemOut(
                version=v.version,
                status=v.status,
                attribution=f"v{v.version} drafted · {by}",
                at=v.created_at,
            )
        )
    return PlanHistoryOut(items=items)


# --- drafts --------------------------------------------------------------------------------------

_NEW_PLAN = text(
    "INSERT INTO close_plans (tenant_id, client_entity_id, created_by) "
    "VALUES (:t, :e, :u) RETURNING id"
)
_NEW_VERSION = text(
    "INSERT INTO close_plan_versions (tenant_id, plan_id, version, drafted_by) "
    "VALUES (:t, :p, :n, :u) RETURNING id"
)
_COPY_ROWS = text(
    "INSERT INTO close_plan_rows (tenant_id, version_id, position, account_external_id, "
    "account_name, account_class, procedure, method, evidence_required, source, review_level, "
    "frequency, threshold_ref) SELECT tenant_id, :to, position, account_external_id, "
    "account_name, account_class, procedure, method, evidence_required, source, review_level, "
    "frequency, threshold_ref FROM close_plan_rows WHERE version_id = :from"
)
_COPY_TEMPLATES = text(
    "INSERT INTO close_request_templates (tenant_id, version_id, title, category_path, "
    "due_business_day, client_visible, source_row_ids) SELECT tenant_id, :to, title, "
    "category_path, due_business_day, client_visible, '{}' FROM close_request_templates "
    "WHERE version_id = :from"
)


async def create_draft(ctx: AuthContext, client_id: UUID, body: PlanDraftIn) -> PlanVersionOut:
    """Draft v(n+1) from `from_version` (default the newest published; a first plan starts
    empty)."""
    _human(ctx, EDIT)
    ref = await _scope(ctx, client_id, EDIT)
    async with uow(ctx.tenant) as tx:
        plan_id = await _plan_id(tx.session, ref.client_entity_id)
        if plan_id is None:
            plan_id = cast(
                UUID,
                await tx.session.scalar(
                    _NEW_PLAN, {"t": ctx.tenant_id, "e": ref.client_entity_id, "u": ctx.user_id}
                ),
            )
        versions = await _versions(tx.session, plan_id)
        if any(v.status == "draft" for v in versions):
            raise DraftExists(facts={"plan_id": str(plan_id)})
        source = None
        if body.from_version is not None:
            source = next((v for v in versions if v.version == body.from_version), None)
            if source is None:
                raise NotFound("close_plan_version")
        else:
            source = next((v for v in reversed(versions) if v.status == "published"), None)
        number = (versions[-1].version if versions else 0) + 1
        try:
            async with tx.session.begin_nested():
                draft = await tx.session.scalar(
                    _NEW_VERSION, {"t": ctx.tenant_id, "p": plan_id, "n": number, "u": ctx.user_id}
                )
        except IntegrityError:
            raise DraftExists(facts={"plan_id": str(plan_id)}) from None
        if source is not None:
            await tx.session.execute(_COPY_ROWS, {"to": draft, "from": source.id})
            await tx.session.execute(_COPY_TEMPLATES, {"to": draft, "from": source.id})
        tx.record(
            "close_plan.drafted",
            target=Target("close_plan", plan_id),
            after=Ref(version=number),
        )
    return await get_plan(ctx, client_id, number)


_NEW_AGENT_VERSION = text(
    "INSERT INTO close_plan_versions (tenant_id, plan_id, version, drafted_by, drafted_by_run_id) "
    "VALUES (:t, :p, :n, :u, :r) RETURNING id"
)


async def new_agent_draft(ctx: AuthContext, client_id: UUID, run_id: UUID) -> tuple[UUID, int]:
    """C-01-T30 (AC-21): an empty draft the planner run fills, drafted by the person who started
    it with the run's id (History reads "<person> via Agent · Close Planner"). One draft at a
    time (409 `draft_exists`)."""
    _human(ctx, DRAFT_FROM_HISTORY)
    ref = await _scope(ctx, client_id, DRAFT_FROM_HISTORY)
    async with uow(ctx.tenant) as tx:
        plan_id = await _plan_id(tx.session, ref.client_entity_id)
        if plan_id is None:
            plan_id = cast(
                UUID,
                await tx.session.scalar(
                    _NEW_PLAN, {"t": ctx.tenant_id, "e": ref.client_entity_id, "u": ctx.user_id}
                ),
            )
        versions = await _versions(tx.session, plan_id)
        if any(v.status == "draft" for v in versions):
            raise DraftExists(facts={"plan_id": str(plan_id)})
        number = (versions[-1].version if versions else 0) + 1
        try:
            async with tx.session.begin_nested():
                draft = cast(
                    UUID,
                    await tx.session.scalar(
                        _NEW_AGENT_VERSION,
                        {"t": ctx.tenant_id, "p": plan_id, "n": number, "u": ctx.user_id,
                         "r": run_id},
                    ),
                )  # fmt: skip
        except IntegrityError:
            raise DraftExists(facts={"plan_id": str(plan_id)}) from None
        tx.record(
            "close_plan.drafted",
            target=Target("close_plan", plan_id),
            after=Ref(version=number, run_id=run_id),
        )
    return draft, number


async def _draft(
    session: AsyncSession, entity: UUID, version: int, seen: int
) -> tuple[UUID, _Row]:
    plan_id = await _plan_id(session, entity)
    if plan_id is None:
        raise NotFound("close_plan")
    found = next((v for v in await _versions(session, plan_id) if v.version == version), None)
    if found is None:
        raise NotFound("close_plan_version")
    if found.status != "draft":
        raise VersionNotDraft(facts={"version": version})
    if found.row_version != seen:
        # Facts carry identifiers only: the screen names the editor from the id (CLS-09 f).
        raise StaleClose(facts={"editor_user_id": str(found.drafted_by)})
    return plan_id, found


_BUMP = text(
    "UPDATE close_plan_versions SET row_version = row_version + 1 WHERE id = :v "
    "AND row_version = :seen RETURNING row_version"
)


async def _bump(session: AsyncSession, version_id: UUID, seen: int) -> None:
    if await session.scalar(_BUMP, {"v": version_id, "seen": seen}) is None:
        raise StaleClose(facts={"version_id": str(version_id)})


def _threshold(policy_version_id: UUID | None) -> str | None:
    return (
        None
        if policy_version_id is None
        else json.dumps({"policy_version_id": str(policy_version_id)})
    )


_PATCHABLE: Final = (
    "procedure",
    "method",
    "evidence_required",
    "source",
    "review_level",
    "frequency",
)


# One fixed statement for every PATCH (SQL-001): each column takes its new value only when the
# body set it; the rest keep theirs.
_PATCH_ROW: Final = text(
    "UPDATE close_plan_rows SET "
    "procedure = CASE WHEN :set_procedure THEN :procedure ELSE procedure END, "
    "method = CASE WHEN :set_method THEN :method ELSE method END, "
    "evidence_required = CASE WHEN :set_evidence_required THEN :evidence_required "
    "ELSE evidence_required END, "
    "source = CASE WHEN :set_source THEN :source ELSE source END, "
    "review_level = CASE WHEN :set_review_level THEN :review_level ELSE review_level END, "
    "frequency = CASE WHEN :set_frequency THEN :frequency ELSE frequency END, "
    "threshold_ref = CASE WHEN :set_threshold_ref THEN CAST(:threshold_ref AS jsonb) "
    "ELSE threshold_ref END "
    "WHERE id = :row AND version_id = :v RETURNING id"
)


async def patch_row(
    ctx: AuthContext,
    client_id: UUID,
    version: int,
    row_id: UUID,
    body: PlanRowPatchIn,
    if_match: str,
) -> PlanRowOut:
    _human(ctx, EDIT)
    ref = await _scope(ctx, client_id, EDIT)
    seen = _seen(if_match)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _PATCHABLE}
    if "threshold_policy_version_id" in body.model_fields_set:
        changes["threshold_ref"] = _threshold(body.threshold_policy_version_id)
    async with uow(ctx.tenant) as tx:
        plan_id, draft = await _draft(tx.session, ref.client_entity_id, version, seen)
        if changes:
            params: dict[str, object] = {"row": row_id, "v": draft.id}
            for k in (*_PATCHABLE, "threshold_ref"):
                params[f"set_{k}"] = k in changes
                params[k] = changes.get(k)
            moved = await tx.session.scalar(_PATCH_ROW, params)
            if moved is None:
                raise NotFound("close_plan_row")
            await _bump(tx.session, draft.id, seen)
            tx.record("close_plan.edited", target=Target("close_plan", plan_id))
        row = (
            await tx.session.execute(
                text(_ROWS.text.replace("WHERE version_id = :v", "WHERE id = :row")),
                {"row": row_id},
            )
        ).first()
    if row is None:
        raise NotFound("close_plan_row")
    return _row_out(row, None)


_ADD_ROW = text(
    "INSERT INTO close_plan_rows (tenant_id, version_id, position, account_external_id, "
    "account_name, account_class, procedure, method, evidence_required, source, review_level, "
    "frequency, threshold_ref) VALUES (:t, :v, (SELECT coalesce(max(position) + 1, 0) "
    "FROM close_plan_rows WHERE version_id = :v), :account_external_id, :account_name, "
    ":account_class, :procedure, :method, :evidence_required, :source, :review_level, "
    ":frequency, CAST(:threshold_ref AS jsonb)) RETURNING id"
)


async def add_row(
    ctx: AuthContext, client_id: UUID, version: int, body: PlanRowIn, if_match: str
) -> PlanRowOut:
    _human(ctx, EDIT)
    ref = await _scope(ctx, client_id, EDIT)
    seen = _seen(if_match)
    values = body.model_dump(exclude={"threshold_policy_version_id"})
    async with uow(ctx.tenant) as tx:
        plan_id, draft = await _draft(tx.session, ref.client_entity_id, version, seen)
        row_id = await tx.session.scalar(
            _ADD_ROW,
            {
                **values,
                "t": ctx.tenant_id,
                "v": draft.id,
                "threshold_ref": _threshold(body.threshold_policy_version_id),
            },
        )
        await _bump(tx.session, draft.id, seen)
        tx.record("close_plan.edited", target=Target("close_plan", plan_id))
        row = (
            await tx.session.execute(
                text(_ROWS.text.replace("WHERE version_id = :v", "WHERE id = :row")),
                {"row": row_id},
            )
        ).first()
    if row is None:
        raise NotFound("close_plan_row")
    return _row_out(row, None)


_ADD_TEMPLATE = text(
    "INSERT INTO close_request_templates (tenant_id, version_id, title, category_path, "
    "due_business_day, client_visible, source_row_ids) VALUES (:t, :v, :title, :category_path, "
    ":due_business_day, :client_visible, '{}') RETURNING id"
)


async def add_request_template(
    ctx: AuthContext, client_id: UUID, version: int, body: RequestTemplateIn, if_match: str
) -> RequestTemplateOut:
    _human(ctx, EDIT)
    ref = await _scope(ctx, client_id, EDIT)
    seen = _seen(if_match)
    async with uow(ctx.tenant) as tx:
        plan_id, draft = await _draft(tx.session, ref.client_entity_id, version, seen)
        template_id = await tx.session.scalar(
            _ADD_TEMPLATE, {**body.model_dump(), "t": ctx.tenant_id, "v": draft.id}
        )
        await _bump(tx.session, draft.id, seen)
        tx.record("close_plan.edited", target=Target("close_plan", plan_id))
    return RequestTemplateOut(template_id=cast(UUID, template_id), **body.model_dump())


# --- publish, request publish, adopt -------------------------------------------------------------

_PUBLISH = text(
    "UPDATE close_plan_versions SET status = 'published', effective_from = :from, "
    "published_by = :u, published_actor_kind = 'human', published_at = abacus_now(), "
    "row_version = row_version + 1 WHERE id = :v AND row_version = :seen RETURNING id"
)
# QC-2: every close of the entity past BD1 and not yet pinned keeps the version it reads now.
_PIN_PAST_BD1 = text(
    "UPDATE closes c SET close_plan_version_id = ("
    "SELECT v.id FROM close_plan_versions v WHERE v.plan_id = :p AND v.status = 'published' "
    "AND v.effective_from <= c.period ORDER BY v.effective_from DESC, v.version DESC LIMIT 1), "
    "plan_pinned_at = abacus_now(), row_version = c.row_version + 1 "
    "WHERE c.client_entity_id = :e AND c.plan_pinned_at IS NULL "
    "AND c.requests_publish_on <= :today AND c.status NOT IN ('delivered', 'locked') "
    "AND EXISTS (SELECT 1 FROM close_plan_versions v WHERE v.plan_id = :p "
    "AND v.status = 'published' AND v.effective_from <= c.period) RETURNING c.work_item_id"
)


async def publish(
    ctx: AuthContext, client_id: UUID, version: int, body: PublishIn, if_match: str
) -> PlanVersionOut:
    """A Manager or Partner publishes with `effective_from` (AC-17); a Senior is 403 (the matrix
    denies `close_plan.publish`)."""
    _human(ctx, PUBLISH)
    ref = await _scope(ctx, client_id, PUBLISH)
    seen = _seen(if_match)
    on = await today(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        plan_id, draft = await _draft(tx.session, ref.client_entity_id, version, seen)
        pinned = list(
            await tx.session.scalars(
                _PIN_PAST_BD1, {"p": plan_id, "e": ref.client_entity_id, "today": on}
            )
        )
        for close_id in pinned:
            tx.record("close.plan_pinned", target=Target("close", close_id))
        try:
            async with tx.session.begin_nested():
                done = await tx.session.scalar(
                    _PUBLISH,
                    {"v": draft.id, "from": body.effective_from, "u": ctx.user_id, "seen": seen},
                )
        except DBAPIError as exc:
            if "unadopted_rows" in str(exc.orig):
                raise UnadoptedRows(facts={"version": version}) from None
            raise
        if done is None:
            raise StaleClose(facts={"version": version})
        tx.record(
            "close_plan.published",
            target=Target("close_plan", plan_id),
            after=Ref(version=version),  # a Ref carries no dates or text
        )
        tx.emit(ClosePlanPublished(plan_id=plan_id, version_id=draft.id, engagement_id=ref.id))
    return await get_plan(ctx, client_id, version)


_REQUEST = text(
    "UPDATE close_plan_versions SET publish_requested_by = :u, "
    "publish_requested_at = abacus_now(), row_version = row_version + 1 "
    "WHERE id = :v AND status = 'draft' AND publish_requested_at IS NULL RETURNING id"
)


async def request_publish(ctx: AuthContext, client_id: UUID, version: int) -> PlanVersionOut:
    """A Senior asks; one gate waits on the engagement's Managers and Partners (QC-8)."""
    _human(ctx, REQUEST)
    ref = await _scope(ctx, client_id, REQUEST)
    async with tenant_session(ctx.tenant) as session:
        plan_id = await _plan_id(session, ref.client_entity_id)
        if plan_id is None:
            raise NotFound("close_plan")
        draft = next((v for v in await _versions(session, plan_id) if v.version == version), None)
    if draft is None:
        raise NotFound("close_plan_version")
    if draft.status != "draft":
        raise VersionNotDraft(facts={"version": version})
    if draft.publish_requested_at is not None:
        return await get_plan(ctx, client_id, version)  # asked already: one gate, nothing written
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(_REQUEST, {"v": draft.id, "u": ctx.user_id}) is None:
            raise StaleClose(facts={"version": version})  # asked or moved since the read
        tx.record("close_plan.publish_requested", target=Target("close_plan", plan_id))
        tx.emit(
            ClosePlanPublishRequested(plan_id=plan_id, version_id=draft.id, engagement_id=ref.id)
        )
    return await get_plan(ctx, client_id, version)


_ADOPT = text(
    "UPDATE close_plan_rows SET adopted_by = :u, adopted_at = abacus_now() "
    "WHERE version_id = :v AND drafted_suggestion_id IS NOT NULL AND adopted_at IS NULL "
    "AND (CAST(:row AS uuid) IS NULL OR id = :row) RETURNING id"
)


async def adopt(
    ctx: AuthContext, client_id: UUID, version: int, row_id: UUID | None, if_match: str
) -> AdoptOut:
    """A person adopts a drafted row, or all of them (AC-22): the agent's suggestion becomes the
    person's row."""
    _human(ctx, ADOPT)
    ref = await _scope(ctx, client_id, EDIT)
    await authorise(ctx, ADOPT, ref.resource())
    seen = _seen(if_match)
    async with uow(ctx.tenant) as tx:
        _, draft = await _draft(tx.session, ref.client_entity_id, version, seen)
        adopted = list(
            await tx.session.scalars(_ADOPT, {"v": draft.id, "u": ctx.user_id, "row": row_id})
        )
        if row_id is not None and not adopted:
            raise NotFound("close_plan_row")
        await _bump(tx.session, draft.id, seen)
        for row in adopted:
            tx.record("close_plan_row.adopted", target=Target("close_plan_row", row))
    return AdoptOut(adopted=len(adopted), row_version=seen + 1)


# --- pinning (QC-2) ------------------------------------------------------------------------------

_PIN = text(
    "UPDATE closes c SET close_plan_version_id = ("
    "SELECT v.id FROM close_plans p JOIN close_plan_versions v ON v.plan_id = p.id "
    "WHERE p.client_entity_id = c.client_entity_id AND v.status = 'published' "
    "AND v.effective_from <= c.period ORDER BY v.effective_from DESC, v.version DESC LIMIT 1), "
    "plan_pinned_at = abacus_now(), row_version = c.row_version + 1 "
    "WHERE c.work_item_id = :id AND c.plan_pinned_at IS NULL RETURNING c.close_plan_version_id"
)


async def pin_plan(session: AsyncSession, close_id: UUID) -> UUID | None:
    """At BD1 (RequestPublishWorkflow, C-01-T19) or a first run: the close keeps the version it
    reads now, for good (the trigger refuses any later change). None when already pinned or no
    version is published for its period."""
    return cast(UUID | None, await session.scalar(_PIN, {"id": close_id}))


# --- templates (AC-20) ---------------------------------------------------------------------------

_LIST_TEMPLATES = text(
    "SELECT DISTINCT ON (key) id, key, name, version, rows, request_templates "
    "FROM close_templates ORDER BY key, version DESC"
)
_IMPORT = text(
    "INSERT INTO close_templates (tenant_id, key, name, version, rows, request_templates, "
    "imported_by) VALUES (:t, :key, :name, :version, CAST(:rows AS jsonb), "
    "CAST(:requests AS jsonb), :u) RETURNING id"
)


def _template_out(
    r: _Row,
) -> CloseTemplateOut:
    stored: object = r.rows
    rows = cast(list[object], stored if isinstance(stored, list) else json.loads(str(stored)))
    raw: object = r.request_templates
    requests = cast(
        list[dict[str, object]], raw if isinstance(raw, list) else json.loads(str(raw))
    )
    return CloseTemplateOut(
        template_id=r.id,
        key=r.key,
        name=r.name,
        version=r.version,
        procedures=len(rows),
        requests=sum(bool(t.get("client_visible", True)) for t in requests),
    )


async def list_templates(ctx: AuthContext) -> CloseTemplatesOut:
    if ctx.client:
        raise NotFound("close_template")
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_LIST_TEMPLATES)).all())
    return CloseTemplatesOut(items=[_template_out(r) for r in rows])


async def import_template(ctx: AuthContext, body: CloseTemplateImportIn) -> CloseTemplateOut:
    """Firm content through an import, never a commit (AC-20). A key's version is written once."""
    _human(ctx, IMPORT)
    await authorise(ctx, IMPORT, Resource.firm(ctx.tenant_id))
    rows = [r.model_dump(mode="json") for r in body.rows]
    requests = [t.model_dump(mode="json") for t in body.request_templates]
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                template_id = await tx.session.scalar(
                    _IMPORT,
                    {
                        "t": ctx.tenant_id,
                        "key": body.key,
                        "name": body.name,
                        "version": body.version,
                        "rows": json.dumps(rows),
                        "requests": json.dumps(requests),
                        "u": ctx.user_id,
                    },
                )
        except IntegrityError:
            raise TemplateExists(facts={"key": body.key, "version": body.version}) from None
        tx.record(
            "close_template.imported", target=Target("close_template", cast(UUID, template_id))
        )
    return CloseTemplateOut(
        template_id=cast(UUID, template_id),
        key=body.key,
        name=body.name,
        version=body.version,
        procedures=len(rows),
        requests=sum(t.client_visible for t in body.request_templates),
    )


__all__ = [
    "add_request_template",
    "add_row",
    "adopt",
    "create_draft",
    "get_plan",
    "import_template",
    "list_templates",
    "new_agent_draft",
    "pin_plan",
    "plan_history",
    "publish",
    "request_publish",
]
