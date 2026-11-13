"""Issues part 2 (P-04-T31; SHL-15; ISSUE-001; DEC-828): resolutions, fix instructions and
send-to-client.

- **Resolve, verify, reopen, not applicable** are a person's acts: the service refuses an agent,
  system or support context before anything is read further (403), the matrix denies them, and
  `issue_events` refuses a `resolved`, `verified` or `marked_not_applicable` row from anyone but
  a person (0094's CHECK). Each moves the status one step from where the registry allows, on the
  version the person saw (409 `issue_changed`), and writes its event and audit row.
- **Fix instructions** (sealed, `this_issue` or `all_of_class`) go to the fix runner registered
  for the issue's kind (`review.slots.register_fix_runner`); with none, nothing is recorded and
  the route answers 409 `fix_runner_unavailable` (fail closed). Bulk decides each on its own.
- **Send to client** makes one request item carrying only the client wording (never the title or
  the internal note), through the registered client-request sender (`agents` registers
  `requests.api.add_request_item`, since review may not import requests), after the engagement's
  G3 is met (409 `gate_unmet`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import gate_fact
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.review.events import IssueStatusChanged
from abacus.modules.review.issue_runs import record_issue_run
from abacus.modules.review.issues import SUBJECT, IssueChanged
from abacus.modules.review.issues import issue_record as _record
from abacus.modules.review.issues import issue_row as _one
from abacus.modules.review.sealing import seal_text
from abacus.modules.review.slots import (
    explainer_registered,
    fix_runner_registered,
    run_explain,
    run_fix,
)

_FROM: Final[dict[str, frozenset[str]]] = {
    "resolved": frozenset({"open", "in_progress", "reopened"}),
    "verified": frozenset({"resolved"}),
    "reopened": frozenset({"resolved", "verified", "not_applicable"}),
    "not_applicable": frozenset({"open", "in_progress", "reopened"}),
}
_EVENT: Final = {
    "resolved": "resolved",
    "verified": "verified",
    "reopened": "reopened",
    "not_applicable": "marked_not_applicable",
}
_ACTION: Final = {
    "resolved": "issue.resolve",
    "verified": "issue.verify",
    "reopened": "issue.reopen",
    "not_applicable": "issue.resolve",
}


class IssueStatusRefused(DomainConflict):
    """The issue cannot move there from where it is (`facts.status`)."""

    code = "issue_status_refused"


class IssueSystemResolvedOnly(DomainConflict):
    """T-04-T23 (TAX-06b, 0800): a dependency issue resolves when its dependency does, by the
    system, never by a person (`POST /v1/issues/{id}/resolve` answers 409)."""

    code = "system_resolved_only"


class FixRunnerUnavailable(DomainConflict):
    """No fix runner is registered: nothing is recorded (fail closed)."""

    code = "fix_runner_unavailable"


class LetterGateUnmet(DomainConflict):
    """The engagement's letter (G3) is not met: nothing goes to the client (ADR-111)."""

    code = "gate_unmet"


ClientRequestSender = Callable[[AuthContext, UUID, str, UUID, date | None], Awaitable[UUID]]
_SENDER: list[ClientRequestSender] = []


def register_client_request_sender(sender: ClientRequestSender) -> None:
    """`(ctx, engagement_id, client_wording, contact_id, due_on) -> request_item_id`."""
    _SENDER[:] = [sender]


def _person(ctx: AuthContext) -> None:
    """ISSUE-001: only a person, as themselves, resolves; never the agent, system or support."""
    if ctx.is_support or ctx.tenant.actor_kind != "human":
        raise Forbidden("issue.resolve", "role")


_MOVE = text(
    "UPDATE issues SET status = :status, version = version + 1 "
    "WHERE id = :id AND version = :v RETURNING id"
)
_EVENT_ROW = text(
    "INSERT INTO issue_events (tenant_id, issue_id, event, fix_instructions_sealed, scope) "
    "VALUES (:t, :i, :event, :sealed, :scope)"
)


async def move(ctx: AuthContext, issue_id: UUID, to: str, seen_version: int) -> None:
    """Resolve, verify, reopen or mark not applicable."""
    _person(ctx)
    current = await _one(ctx.tenant, issue_id)
    _, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, _ACTION[to], resource)
    if current.status not in _FROM[to]:
        raise IssueStatusRefused(facts={"status": current.status})
    if to in ("resolved", "not_applicable") and await _system_only(ctx.tenant, issue_id):
        raise IssueSystemResolvedOnly
    async with uow(ctx.tenant) as tx:
        if (
            await tx.session.execute(_MOVE, {"status": to, "id": issue_id, "v": seen_version})
        ).first() is None:
            raise IssueChanged(facts={"version": current.version})
        await tx.session.execute(
            _EVENT_ROW,
            {
                "t": ctx.tenant_id,
                "i": issue_id,
                "event": _EVENT[to],
                "sealed": None,
                "scope": None,
            },
        )
        tx.record(
            f"issue.{_EVENT[to]}",
            target=Target(SUBJECT, issue_id),
            before=Ref(version=current.version),
            after=Ref(version=current.version + 1),
            scope=Scope(engagement_id=current.engagement_id),
        )
        tx.emit(
            IssueStatusChanged(issue_id=issue_id, engagement_id=current.engagement_id, status=to)
        )


async def _system_only(tenant: TenantContext, issue_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        return bool(
            await session.scalar(
                text("SELECT system_resolved_only FROM issues WHERE id = :i"), {"i": issue_id}
            )
        )


_SYSTEM_DEPENDENTS = text(
    "SELECT id, version, engagement_id FROM issues WHERE source_kind = 'k1_dependency' "
    "AND system_resolved_only AND source_ref = :ref AND status IN ('open', 'in_progress', "
    "'reopened') FOR UPDATE"
)


async def system_resolve_dependents(system: TenantContext, source_ref: str) -> list[UUID]:
    """T-04-T23 (AC-4.2): the open dependency issues named `source_ref` (the Draft K-1 issue's
    `k1_dependency:<package>`) resolve as the system once their dependency is met: status
    `resolved`, a `system_resolved` event (0800: the system only), one audit event each."""
    if system.actor_kind != "system":
        raise Forbidden("issue.system_resolve", "role")
    resolved: list[UUID] = []
    async with uow(system) as tx:
        rows = (await tx.session.execute(_SYSTEM_DEPENDENTS, {"ref": source_ref})).all()
        for row in rows:
            await tx.session.execute(
                text("UPDATE issues SET status = 'resolved', version = version + 1 WHERE id = :i"),
                {"i": row.id},
            )
            await tx.session.execute(
                _EVENT_ROW,
                {
                    "t": system.tenant_id,
                    "i": row.id,
                    "event": "system_resolved",
                    "sealed": None,
                    "scope": None,
                },
            )
            tx.record(
                "issue.system_resolved",
                target=Target(SUBJECT, row.id),
                before=Ref(version=int(row.version)),
                after=Ref(version=int(row.version) + 1),
                scope=Scope(engagement_id=row.engagement_id),
            )
            tx.emit(
                IssueStatusChanged(
                    issue_id=row.id, engagement_id=row.engagement_id, status="resolved"
                )
            )
            resolved.append(row.id)
    return resolved


async def system_resolve_self_checks(
    system: TenantContext, work_item_id: UUID, source_refs: Sequence[str]
) -> list[UUID]:
    """T-05-T42 (0860, DEC-4705): the open `self_check` issues of a work item named by
    `source_refs` resolve as the system once their check passes (a `system_resolved` event and
    one audit event each). Only issues raised `system_resolved_only` move."""
    if system.actor_kind != "system":
        raise Forbidden("issue.system_resolve", "role")
    if not source_refs:
        return []
    resolved: list[UUID] = []
    async with uow(system) as tx:
        rows = (
            await tx.session.execute(
                text(
                    "SELECT id, version, engagement_id FROM issues WHERE work_item_id = :w "
                    "AND source_kind = 'self_check' AND system_resolved_only "
                    "AND source_ref = ANY(:refs) AND status IN ('open', 'in_progress', "
                    "'reopened') FOR UPDATE"
                ),
                {"w": work_item_id, "refs": list(source_refs)},
            )
        ).all()
        for row in rows:
            await tx.session.execute(
                text("UPDATE issues SET status = 'resolved', version = version + 1 WHERE id = :i"),
                {"i": row.id},
            )
            await tx.session.execute(
                _EVENT_ROW,
                {
                    "t": system.tenant_id,
                    "i": row.id,
                    "event": "system_resolved",
                    "sealed": None,
                    "scope": None,
                },
            )
            tx.record(
                "issue.system_resolved",
                target=Target(SUBJECT, row.id),
                before=Ref(version=int(row.version)),
                after=Ref(version=int(row.version) + 1),
                scope=Scope(engagement_id=row.engagement_id),
            )
            tx.emit(
                IssueStatusChanged(
                    issue_id=row.id, engagement_id=row.engagement_id, status="resolved"
                )
            )
            resolved.append(row.id)
    return resolved


async def set_fix_instructions(
    ctx: AuthContext, issue_id: UUID, seen_version: int, instructions: str, scope: str
) -> UUID:
    """Seal the instructions, start the fix run; 409 `fix_runner_unavailable` with no runner."""
    current = await _one(ctx.tenant, issue_id)
    _, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, "fix_instruction.set", resource)
    if not fix_runner_registered(current.record_type):
        raise FixRunnerUnavailable
    if current.version != seen_version:
        raise IssueChanged(facts={"version": current.version})
    sealed = await seal_text(ctx.tenant, instructions, SUBJECT, issue_id, "fix_instructions")
    starts = current.status in (
        "open",
        "reopened",
    )  # T-04-T31 (AC-4.3): the issue goes In progress
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _EVENT_ROW,
            {
                "t": ctx.tenant_id,
                "i": issue_id,
                "event": "fix_instructions_set",
                "sealed": sealed,
                "scope": scope,
            },
        )
        if starts:
            moved = await tx.session.execute(
                _MOVE, {"status": "in_progress", "id": issue_id, "v": seen_version}
            )
            if moved.first() is None:
                raise IssueChanged(facts={"version": current.version})
            await tx.session.execute(
                _EVENT_ROW,
                {
                    "t": ctx.tenant_id,
                    "i": issue_id,
                    "event": "status_changed",
                    "sealed": None,
                    "scope": None,
                },
            )
        tx.record(
            "issue.fix_instructions_set",
            target=Target(SUBJECT, issue_id),
            before=Ref(version=current.version),
            after=Ref(version=current.version + int(starts)),
            scope=Scope(engagement_id=current.engagement_id),
        )
    # The run is the person's (their `agent_run.start`); its row ties it to this issue only.
    run = await run_fix(ctx, current.record_type, issue_id)
    await record_issue_run(ctx, issue_id, run, "fix")
    return run


class ExplainUnavailable(DomainConflict):
    """No explainer is registered for the issue's record type (fail closed, T-04-T31)."""

    code = "explain_unavailable"


async def explain(ctx: AuthContext, issue_id: UUID) -> UUID:
    """SHL-15 d, "Explain…" (T-04-T31): a person asks; the record type's explainer runs as their
    run and stores only verified citations. Nothing is decided and the issue does not move."""
    current = await _one(ctx.tenant, issue_id)
    _, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, "issue.explain", resource)
    if not explainer_registered(current.record_type):
        raise ExplainUnavailable
    run = await run_explain(ctx, current.record_type, issue_id)
    await record_issue_run(ctx, issue_id, run, "explain")
    return run


@dataclass(frozen=True)
class BulkOutcome:
    issue_id: UUID
    agent_run_id: UUID | None
    code: str | None


async def set_fix_instructions_bulk(
    ctx: AuthContext, items: list[tuple[UUID, int]], instructions: str, scope: str
) -> list[BulkOutcome]:
    """Each issue on its own: one refusal never stops the others."""
    out: list[BulkOutcome] = []
    for issue_id, seen in items:
        try:
            run = await set_fix_instructions(ctx, issue_id, seen, instructions, scope)
            out.append(BulkOutcome(issue_id, run, None))
        except DomainConflict as refused:
            out.append(BulkOutcome(issue_id, None, refused.code))
    return out


async def check_send(ctx: AuthContext, issue_id: UUID) -> None:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too."""
    current = await _one(ctx.tenant, issue_id)
    _, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, "issue.send_to_client", resource)


async def send_to_client(
    ctx: AuthContext,
    issue_id: UUID,
    *,
    seen_version: int,
    client_wording: str,
    contact_id: UUID,
    due_on: date | None,
) -> UUID:
    """One client-visible request item with only the client wording; returns its id."""
    current = await _one(ctx.tenant, issue_id)
    engagement_id, resource, _ = await _record(ctx, current.record_type, current.record_id)
    await authorise(ctx, "issue.send_to_client", resource)
    if current.version != seen_version:
        raise IssueChanged(facts={"version": current.version})
    if not (await gate_fact(ctx.tenant, engagement_id, "G3")).met:
        raise LetterGateUnmet(facts={"gate": "G3"})
    if not _SENDER:
        raise FixRunnerUnavailable  # no sender registered: refuse closed, nothing sent
    item = await _SENDER[0](ctx, engagement_id, client_wording, contact_id, due_on)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _EVENT_ROW,
            {
                "t": ctx.tenant_id,
                "i": issue_id,
                "event": "sent_to_client",
                "sealed": None,
                "scope": None,
            },
        )
        await tx.session.execute(
            text(
                "INSERT INTO issue_links (tenant_id, issue_id, link_kind, ref) "
                "VALUES (:t, :i, 'request_item', jsonb_build_object('id', CAST(:item AS text)))"
            ),
            {"t": ctx.tenant_id, "i": issue_id, "item": str(item)},
        )
        tx.record(
            "issue.sent_to_client",
            target=Target(SUBJECT, issue_id),
            after=Ref(request_item_id=item),
            scope=Scope(engagement_id=current.engagement_id),
        )
    return item
