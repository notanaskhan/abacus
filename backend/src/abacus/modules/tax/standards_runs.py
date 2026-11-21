"""Standards runs (T-08-T14; TASK-8838; T-08 §3; SPEC-710 AC-26; TAX-14; ADR-050, ADR-005;
DEC-5840). Amber. No model is called anywhere in TAX-14 (OQ-3).

- **Start** (`standards_run.start`, a live person, firm-wide): pins a published `review_checklist`
  version (K-02, `applies_to.form`) and the selected returns of that form the person may see
  (`visible()` through `work_item_facts`), writes the run and one queued item per return, and
  starts `StandardsRunWorkflow`, which fans out one activity per return.
- **Checks.** Each checklist item with a `check_code` runs that code's check (the registration slot
  of T-08-T13; this module registers the workbook tie-out checks it owns); an item without one is
  `manual_pending` until a reviewer confirms it (`standards_check.confirm`, human only). Results
  are insert-only, keyed `<form>-v<n>/<code>` with the check's anchor (sheet and range).
- **Issues, deduplicated.** An exception whose check already has an open issue on the return
  (`tie_out:<key>`) links it (Ridgeline's two: its count stays 11); otherwise the run raises one
  self-check issue under the same reference as the system (Marlowe's three), in the
  `standards_runs` category (HOME-02's source facet). A re-run never raises a second: the
  reference is the dedupe key.
- **Progress.** Each finished item emits `standards_run.progressed` (identifiers only), which the
  realtime topic `standards_run:<id>` invalidates, so TAX-14's tiles move live.
- **Re-run** on a selection starts a new run of the same version over those returns.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import RetryPolicy

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.tax.standards_run_workflow import (
    FINISH_ACTIVITY,
    ITEM_ACTIVITY,
    ITEMS_ACTIVITY,
    StandardsRunWorkflow,
)

if TYPE_CHECKING:
    from abacus.modules.identity.api import AuthContext

READ: Final = "standards_run.read"
START: Final = "standards_run.start"
CONFIRM: Final = "standards_check.confirm"
TARGET: Final = "standards_run"
CATEGORY: Final = "standards_runs"
_DISPLAY: Final = re.compile(r"^[A-Za-z]-\d{2,3}$")
Outcome = Literal["pass", "exception", "manual_pending", "not_applicable"]


class StandardNotChecklist(DomainConflict):
    code = "standard_not_checklist"


class CheckAlreadyConfirmed(DomainConflict):
    code = "check_already_confirmed"


@dataclass(frozen=True)
class TieOutResult:
    outcome: Outcome
    difference: Decimal | None = None
    anchor: dict[str, str] | None = None
    issue_ref: str | None = None  # the open issue a failure links, or raises under
    title: str | None = None


Check = Callable[[TenantContext, UUID, Decimal | None], Awaitable[TieOutResult]]
_CHECKS: dict[str, Check] = {}


def register_check(code: str, description: str, check: Check) -> None:
    """A check's owner: its code joins the checklist registry (T-08-T13) and its function runs."""
    from abacus.modules.methodology.api import register_check_code

    register_check_code(code, description)
    _CHECKS[code] = check


def _tie_out(key: str) -> Check:
    async def run(tenant: TenantContext, return_id: UUID, _t: Decimal | None) -> TieOutResult:
        from abacus.modules.review.api import current_values
        from abacus.modules.tax.entity_sections import tie_outs
        from abacus.modules.tax.workbook_service import WORKBOOK

        found = next(
            (
                t
                for t in tie_outs(await current_values(tenant, WORKBOOK, return_id))
                if t.key == key
            ),
            None,
        )
        if found is None or found.state == "pending":
            return TieOutResult("not_applicable")
        link = dict(found.links[0]) if found.links else None
        if found.state == "tie":
            return TieOutResult("pass", found.difference, link)
        return TieOutResult(
            "exception",
            found.difference,
            link,
            f"tie_out:{key}",
            f"{found.label}: off {abs(found.difference or Decimal(0)):,.0f}",
        )

    return run


TIE_OUT_CHECKS: Final = {
    "tie_out.tb_foots": ("tb_foots", "Trial balance foots"),
    "tie_out.capital_rollforward": ("capital_rollforward", "Capital rolls forward"),
    "tie_out.item_l_m2": ("item_l_m2", "Item L ties M-2"),
    "tie_out.k1_sum_k": ("k1_sum_k", "Σ K-1 = Schedule K"),
}


class StandardsRunProgressed(DomainEvent):
    """One return of a standards run finished (TAX-14's live tiles). Identifiers only."""

    event_type: ClassVar[str] = "standards_run.progressed"

    run_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]


def check_key(form: str, version_no: int, item_key: str) -> str | None:
    """`1065-v4/C-17` from the item's key (`c-17`); None when the key is not a display code."""
    if not _DISPLAY.match(item_key):
        return None
    return f"{form.lower()}-v{version_no}/{item_key.upper()}"


def _tenant(ctx: object) -> TenantContext:
    """The caller's tenant: every caller here is a person's context (the routes are human)."""
    return cast("AuthContext", ctx).tenant  # a person: the standards routes admit humans only


async def _checklist(ctx: object, version_id: UUID) -> tuple[str, int, dict[str, object]]:
    from abacus.modules.methodology.api import checklist_version

    found = await checklist_version(_tenant(ctx), version_id)
    if found is None:
        raise StandardNotChecklist(facts={"standard_version_id": str(version_id)})
    return found


async def start(ctx: object, version_id: UUID, return_ids: list[UUID]) -> UUID:
    """A person's run over the selected returns (module docstring)."""
    from abacus.modules.engagements.api import work_item_facts
    from abacus.modules.identity.api import Forbidden, Resource, authorise

    person = cast("AuthContext", ctx)  # a person: the route admits human actors only
    if person.tenant.actor_kind != "human" or person.client or person.is_support:
        raise Forbidden(START, "role")
    await authorise(person, START, Resource.firm(person.tenant_id))
    form, _version_no, _payload = await _checklist(person, version_id)
    visible = {
        f.work_item_id: f for f in await work_item_facts(person, "tax_return", "tax_return.read")
    }
    async with tenant_session(person.tenant) as session:
        forms = {
            UUID(str(r.work_item_id)): str(r.form).lower()
            for r in await session.execute(
                text("SELECT work_item_id, form FROM tax_returns WHERE work_item_id = ANY(:ids)"),
                {"ids": [i for i in return_ids if i in visible]},
            )
        }
    chosen = [i for i in return_ids if forms.get(i) == form.lower()]
    if not chosen:
        raise NotFound("tax_return")
    async with uow(person.tenant) as tx:
        run_id = UUID(
            str(
                (
                    await tx.session.execute(
                        text(
                            "INSERT INTO standards_runs (tenant_id, standard_version_id, form, "
                            "started_by) VALUES (:t, :v, :f, :by) RETURNING id"
                        ),
                        {
                            "t": person.tenant_id,
                            "v": version_id,
                            "f": form.lower(),
                            "by": person.user_id,
                        },
                    )
                ).scalar_one()
            )
        )
        for return_id in chosen:
            f = visible[return_id]
            await tx.session.execute(
                text(
                    "INSERT INTO standards_run_items (tenant_id, engagement_id, work_item_id, "
                    "run_id, checks_total) VALUES (:t, :e, :w, :r, 0)"
                ),
                {"t": person.tenant_id, "e": f.engagement_id, "w": return_id, "r": run_id},
            )
        tx.record(
            "standards_run.started", target=Target(TARGET, run_id), after=Ref(returns=len(chosen))
        )
    await _dispatch(person.tenant_id, run_id)
    return run_id


async def rerun(ctx: object, run_id: UUID, return_ids: list[UUID]) -> UUID:
    async with tenant_session(_tenant(ctx)) as session:
        version = await session.scalar(
            text("SELECT standard_version_id FROM standards_runs WHERE id = :r"), {"r": run_id}
        )
    if version is None:
        raise NotFound(TARGET)
    return await start(ctx, UUID(str(version)), return_ids)


async def _dispatch(tenant_id: UUID, run_id: UUID) -> None:
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from abacus.kernel.dispatch import dispatch

    await dispatch(
        StandardsRunWorkflow,
        [str(tenant_id), str(run_id)],
        id=f"standards_run:{tenant_id}:{run_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


def _system(tenant_id: UUID, run_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"standards_run:{run_id}")


async def items_of(tenant_id: UUID, run_id: UUID) -> list[str]:
    system = _system(tenant_id, run_id)
    async with tenant_session(system) as session:
        rows = await session.execute(
            text("SELECT id FROM standards_run_items WHERE run_id = :r ORDER BY id"), {"r": run_id}
        )
        ids = [str(r.id) for r in rows]
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE standards_runs SET status = 'running' WHERE id = :r AND status = 'queued'"
            ),
            {"r": run_id},
        )
        tx.record("standards_run.running", target=Target(TARGET, run_id))
    return ids


async def run_item(tenant_id: UUID, run_id: UUID, item_id: UUID) -> str:
    """One return's checks, its results and its issues (module docstring), once."""
    from abacus.modules.methodology.api import checklist_version
    from abacus.modules.review.api import open_issue_for_ref, record_self_check_issue

    system = _system(tenant_id, run_id)
    async with tenant_session(system) as session:
        row = (
            await session.execute(
                text(
                    "SELECT i.work_item_id, i.engagement_id, i.status, r.standard_version_id "
                    "FROM standards_run_items i JOIN standards_runs r ON r.id = i.run_id "
                    "WHERE i.id = :i"
                ),
                {"i": item_id},
            )
        ).first()
    if row is None:
        raise NotFound("standards_run_item")
    if str(row.status) not in ("queued", "running"):
        return str(row.status)  # a replayed activity: the item is done
    found = await checklist_version(system, UUID(str(row.standard_version_id)))
    if found is None:
        raise NotFound("standard_version")
    form, version_no, payload = found
    threshold = payload.get("two_year_threshold_pct")
    t = None if threshold is None else Decimal(str(threshold))
    return_id, engagement_id = UUID(str(row.work_item_id)), UUID(str(row.engagement_id))
    results: list[tuple[str, TieOutResult, UUID | None, UUID | None]] = []
    for item in cast(list[dict[str, object]], payload.get("items") or []):
        key = check_key(form, version_no, str(item.get("key", "")))
        if key is None:
            continue
        code = item.get("check_code")
        check = _CHECKS.get(str(code)) if code else None
        result = (
            TieOutResult("manual_pending") if check is None else await check(system, return_id, t)
        )
        linked = created = None
        if result.outcome == "exception" and result.issue_ref is not None:
            linked = await open_issue_for_ref(system, return_id, result.issue_ref)
            if linked is None:
                created, _moved = await record_self_check_issue(
                    system,
                    engagement_id=engagement_id,
                    work_item_id=return_id,
                    record_type="tax_return",
                    record_id=return_id,
                    source_ref=result.issue_ref,
                    title=result.title or key,
                    internal_note=f"Standards run check {key}",
                    links=[result.anchor] if result.anchor else [],
                    category_path=CATEGORY,
                )
        results.append((key, result, linked, created))
    passed = sum(1 for _k, r, _l, _c in results if r.outcome in ("pass", "not_applicable"))
    exceptions = sum(1 for _k, r, _l, _c in results if r.outcome == "exception")
    status = "exceptions" if exceptions else "passed"
    import json

    async with uow(system) as tx:
        for key, r, linked, created in results:
            await tx.session.execute(
                text(
                    "INSERT INTO standards_check_results (tenant_id, run_item_id, check_key, "
                    "outcome, difference, anchor, linked_issue_id, created_issue_id) VALUES (:t, "
                    ":i, :k, :o, :d, CAST(:a AS jsonb), :l, :c) "
                    "ON CONFLICT (run_item_id, check_key) DO NOTHING"
                ),
                {
                    "t": tenant_id,
                    "i": item_id,
                    "k": key,
                    "o": r.outcome,
                    "d": r.difference,
                    "a": None if r.anchor is None else json.dumps(r.anchor),
                    "l": linked,
                    "c": created,
                },
            )
        await tx.session.execute(
            text(
                "UPDATE standards_run_items SET status = :s, checks_total = :n, "
                "checks_passed = :p, completed_at = clock_timestamp() WHERE id = :i"
            ),
            {"s": status, "n": len(results), "p": passed, "i": item_id},
        )
        tx.emit(StandardsRunProgressed(run_id=run_id, work_item_id=return_id))
        tx.record(
            "standards_run.item_checked",
            target=Target(TARGET, run_id),
            after=Ref(item=item_id, exceptions=exceptions),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return status


async def finish(tenant_id: UUID, run_id: UUID) -> str:
    system = _system(tenant_id, run_id)
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE standards_runs SET status = 'complete', completed_at = clock_timestamp() "
                "WHERE id = :r AND status <> 'complete'"
            ),
            {"r": run_id},
        )
        tx.record("standards_run.completed", target=Target(TARGET, run_id))
    return "complete"


# --- StandardsRunWorkflow ------------------------------------------------------------------------

_RETRY: Final = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=["NotFound"],
)


@activity.defn(name=ITEMS_ACTIVITY)
async def items_activity(given: list[str]) -> list[str]:
    return await items_of(UUID(given[0]), UUID(given[1]))


@activity.defn(name=ITEM_ACTIVITY)
async def item_activity(given: list[str]) -> str:
    return await run_item(UUID(given[0]), UUID(given[1]), UUID(given[2]))


@activity.defn(name=FINISH_ACTIVITY)
async def finish_activity(given: list[str]) -> str:
    return await finish(UUID(given[0]), UUID(given[1]))


WORKFLOWS: Final[dict[type, WorkClass]] = {StandardsRunWorkflow: "background"}
ACTIVITIES: Final[tuple[object, ...]] = (items_activity, item_activity, finish_activity)


async def confirm(ctx: object, result_id: UUID, outcome: str, note: str | None) -> None:
    """A reviewer confirms a manual item (`standards_check.confirm`, human only), once."""
    from abacus.modules.identity.api import Forbidden, Resource, authorise

    person = cast("AuthContext", ctx)  # a person: the route admits human actors only
    if person.tenant.actor_kind != "human" or person.client or person.is_support:
        raise Forbidden(CONFIRM, "role")
    await authorise(person, CONFIRM, Resource.firm(person.tenant_id))
    async with uow(person.tenant) as tx:
        done = await tx.session.scalar(
            text(
                "INSERT INTO standards_check_confirmations (tenant_id, result_id, outcome, note, "
                "confirmed_by) VALUES (:t, :r, :o, :n, :by) ON CONFLICT (result_id) DO NOTHING "
                "RETURNING id"
            ),
            {"t": person.tenant_id, "r": result_id, "o": outcome, "n": note, "by": person.user_id},
        )
        if done is None:
            raise CheckAlreadyConfirmed(facts={"result_id": str(result_id)})
        tx.record("standards_check.confirmed", target=Target("standards_check_result", result_id))


def register() -> None:
    """At the tax api's import: the tie-out checks and the run's realtime topic."""
    from abacus.kernel import realtime

    for code, (key, label) in TIE_OUT_CHECKS.items():
        register_check(code, label, _tie_out(key))
    if realtime.invalidation_of(StandardsRunProgressed.event_type) is None:
        realtime.register_invalidation(
            StandardsRunProgressed.event_type,
            realtime.Invalidation("standards_run", "run_id", (("work_item", "work_item_id"),)),
        )


# T-08-T14: the background class routes `dispatch` (ADR-071); one registration, at import.
register_work_classes(WORKFLOWS)

__all__ = [
    "ACTIVITIES",
    "TIE_OUT_CHECKS",
    "WORKFLOWS",
    "StandardsRunWorkflow",
    "TieOutResult",
    "check_key",
    "confirm",
    "finish",
    "register",
    "register_check",
    "rerun",
    "run_item",
    "start",
]


# --- reads (TAX-14) ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunItemView:
    work_item_id: UUID
    client_name: str
    status: str
    checks_total: int
    checks_passed: int
    exceptions: int
    linked: int
    created: int


@dataclass(frozen=True)
class RunView:
    run_id: UUID
    version_id: UUID
    label: str
    form: str
    status: str
    started_at: object
    completed_at: object | None
    items: tuple[RunItemView, ...]


_RUN: Final = text(
    "SELECT r.id, r.standard_version_id, r.form, r.status, r.started_at, r.completed_at "
    "FROM standards_runs r WHERE (:r IS NULL OR r.id = :r) AND (:f IS NULL OR r.form = :f) "
    "AND (:s IS NULL OR r.status = :s) ORDER BY r.started_at DESC LIMIT 50"
)
_ITEMS: Final = text(
    "SELECT i.run_id, i.work_item_id, i.status, i.checks_total, i.checks_passed, "
    "count(c.id) FILTER (WHERE c.outcome = 'exception') AS exceptions, "
    "count(c.linked_issue_id) AS linked, count(c.created_issue_id) AS created "
    "FROM standards_run_items i LEFT JOIN standards_check_results c ON c.run_item_id = i.id "
    "WHERE i.run_id = ANY(:runs) GROUP BY i.id ORDER BY i.id"
)


async def runs(
    ctx: object, run_id: UUID | None = None, form: str | None = None, status: str | None = None
) -> list[RunView]:
    """TAX-14's runs, each item a return the viewer may see (`visible()`; others are absent)."""
    from abacus.modules.engagements.api import work_item_facts
    from abacus.modules.identity.api import Resource, authorise

    person = cast("AuthContext", ctx)  # a person: the route admits human actors only
    await authorise(person, READ, Resource.firm(person.tenant_id))
    visible = {
        f.work_item_id: f for f in await work_item_facts(person, "tax_return", "tax_return.read")
    }
    async with tenant_session(person.tenant) as session:
        found = (
            await session.execute(
                _RUN, {"r": run_id, "f": None if form is None else form.lower(), "s": status}
            )
        ).all()
        items: list[Any] = (  # Any: SQL rows
            list((await session.execute(_ITEMS, {"runs": [r.id for r in found]})).all())
            if found
            else []
        )
    by_run: dict[UUID, list[RunItemView]] = {}
    for i in items:
        w = UUID(str(i.work_item_id))
        if w not in visible:
            continue
        by_run.setdefault(UUID(str(i.run_id)), []).append(
            RunItemView(
                w,
                visible[w].client_name,
                str(i.status),
                int(i.checks_total),
                int(i.checks_passed),
                int(i.exceptions),
                int(i.linked),
                int(i.created),
            )
        )
    out: list[RunView] = []
    for r in found:
        rid = UUID(str(r.id))
        out.append(
            RunView(
                rid,
                UUID(str(r.standard_version_id)),
                f"{str(r.form).upper()} Review Checklist",
                str(r.form),
                str(r.status),
                r.started_at,
                r.completed_at,
                tuple(by_run.get(rid, [])),
            )
        )
    return out


async def checks(ctx: object, run_id: UUID, work_item_id: UUID) -> list[dict[str, object]]:
    found = await runs(ctx, run_id)
    if not found or all(i.work_item_id != work_item_id for i in found[0].items):
        raise NotFound("standards_run_item")
    async with tenant_session(_tenant(ctx)) as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT c.id, c.check_key, c.outcome, c.difference, c.linked_issue_id, "
                        "c.created_issue_id, f.outcome AS confirmed FROM standards_check_results "
                        "c "
                        "JOIN standards_run_items i ON i.id = c.run_item_id LEFT JOIN "
                        "standards_check_confirmations f ON f.result_id = c.id WHERE i.run_id = "
                        ":r "
                        "AND i.work_item_id = :w ORDER BY c.check_key"
                    ),
                    {"r": run_id, "w": work_item_id},
                )
            )
            .mappings()
            .all()
        )
    return [dict(r) for r in rows]
