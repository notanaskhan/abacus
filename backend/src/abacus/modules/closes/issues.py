"""Close issues and transaction questions (C-01-T24; C-01 §3 F8; CLS-06; POR-11 b, c).

- **Producers on P-04's issues service.** A close is a reviewable record (`close`, its facts from
  the close row). `raise_exception` writes a `close_exception`: P-04 kind `exception`, priority =
  the severity band (high, medium, low), category path `close/<class>` (bank_rec, schedule,
  flux, recategorize, intake); an engine's exception is deduplicated on its `source_ref`
  (`close:<class>:<account>:<line>`), so a recompute never raises the same exception twice.
  `add_note` writes a `close_note` (kind `review_point`, path `close_note/<class>`): notes are
  listed and never counted (US-8.1).
- **The Review badge** (`open_exceptions`) counts open exceptions only: Medium 2 + Low 5 = 7 =
  CLS-02's Open Issues; resolved, verified and not-applicable issues and every note are out.
- **An assignee may be a client contact** (P-04's `client_contact_id`).
- **Transaction questions** (DV-7): a person sends the firm's DB template wording with code facts
  (the issue's account and register line; P-25 off, so no agent wording, DEC-79). The send
  authorises `transaction_question.send` on the engagement and runs the outbound scope check
  (`communications.check_scope`, ADR-065): any name, account or amount outside the engagement
  refuses 409 `out_of_scope` with the violation kinds, never the text. The question is written by
  the shared requests API (`requests.transaction_questions`) on the close's intake binder; the
  client's answer marks the issue's kind line "Client answered" and fulfils the linked request.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import uow
from abacus.modules.agents.api import register_suggestion_target
from abacus.modules.closes import repository as repo
from abacus.modules.closes.contract_work import (
    CloseIssueOut,
    CloseIssuesOut,
    Severity,
    TransactionQuestionIn,
    TransactionQuestionOut,
)
from abacus.modules.communications.api import check_scope
from abacus.modules.engagements.api import engagement_resource_of, get_ref
from abacus.modules.identity.api import Actor, AuthContext, Forbidden, authorise
from abacus.modules.requests.api import (
    QuestionRow,
    ask_transaction_question,
    close_intake_binder,
    questions_for,
)
from abacus.modules.review.api import (
    IssueSource,
    ReviewableFacts,
    create_issue,
    list_issues,
    open_text,
    read_issue,
    register_reviewable_facts,
)

CLOSE_TARGET: Final = "close"
ISSUE_SUBJECT: Final = "issue"
IssueClass = Literal["bank_rec", "schedule", "flux", "recategorize", "intake", "posting"]
ISSUE_CLASSES: Final[tuple[IssueClass, ...]] = (
    "bank_rec",
    "schedule",
    "flux",
    "recategorize",
    "intake",
)
EXCEPTION_PATH: Final = "close"
NOTE_PATH: Final = "close_note"
OPEN_STATUSES: Final = frozenset({"open", "in_progress", "reopened", "under_evaluation"})
SEND: Final = "transaction_question.send"


class OutOfScope(DomainConflict):
    code = "out_of_scope"


class NoCloseRequests(DomainConflict):
    """The close's requests are not published yet: a question has no binder to sit on."""

    code = "close_requests_not_published"


class NotACloseIssue(NotFound):
    pass


# --- the reviewable -----------------------------------------------------------------------------


async def close_facts(tenant: TenantContext, close_id: UUID) -> ReviewableFacts | None:
    """The close as a reviewable: issues sit on it (P-04's record ref)."""
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        return None
    digest = hashlib.sha256(
        f"{close.work_item_id}:{close.status}:{close.run_no}:{close.row_version}".encode()
    ).hexdigest()
    return ReviewableFacts(
        target_type=CLOSE_TARGET,
        target_id=close_id,
        engagement_id=close.engagement_id,
        content_hash=digest,
        version_no=max(1, close.row_version),
        preparer_user_ids=frozenset(),
        locked=close.locked_at is not None,
        label=f"Close {close.period}",
        work_item_id=close_id,
    )


register_reviewable_facts(CLOSE_TARGET, close_facts)


_ITEM_CLOSE: Final = text(
    "SELECT r.close_id FROM reconciling_items i JOIN reconciliations r "
    "ON r.id = i.reconciliation_id WHERE i.id = :i"
)


async def reconciling_item_engagement(tenant: TenantContext, item_id: UUID) -> UUID | None:
    """C-01-T28: a reconciling item's engagement (the AJE-draft suggestion's target)."""
    async with tenant_session(tenant) as session:
        close_id = await session.scalar(_ITEM_CLOSE, {"i": item_id})
        close = None if close_id is None else await repo.close_row(session, close_id)
    return None if close is None else close.engagement_id


register_suggestion_target("reconciling_item", engagement_of=reconciling_item_engagement)


# --- producers -----------------------------------------------------------------------------------


def source_ref(issue_class: IssueClass, account_ref: str | None, line_ref: str | None) -> str:
    return f"close:{issue_class}:{account_ref or '-'}:{line_ref or '-'}"[:200]


def _parse(ref: str | None) -> tuple[str | None, str | None]:
    if not ref or not ref.startswith("close:"):
        return None, None
    parts = ref.split(":", 3)
    if len(parts) != 4:
        return None, None
    account, line = parts[2], parts[3]
    return (None if account == "-" else account), (None if line == "-" else line)


async def raise_exception(
    ctx: Actor,  # C-01-T20 rest (DEC-5432): the close run's agent raises through its task scope
    close_id: UUID,
    *,
    severity: Severity,
    issue_class: IssueClass,
    title: str,
    why: str | None = None,
    account_ref: str | None = None,
    register_line_ref: str | None = None,
    engine: bool = True,
    assignee_user_id: UUID | None = None,
    assignee_contact_id: UUID | None = None,
) -> UUID:
    """A `close_exception` on the close (deduplicated by its source for an engine's)."""
    return await create_issue(
        ctx,
        record_type=CLOSE_TARGET,
        record_id=close_id,
        kind="exception",
        priority=severity,
        title=title,
        internal_note=why,
        client_wording=None,
        client_contact_id=assignee_contact_id,
        assignee_user_id=assignee_user_id,
        assignee_agent=False,
        blocks=(),
        source_ref=source_ref(issue_class, account_ref, register_line_ref) if engine else None,
        work_item_id=close_id,
        source=IssueSource(
            kind="engine_diagnostic" if engine else "manual",
            category_path=f"{EXCEPTION_PATH}/{issue_class}",
        ),
    )


async def add_note(
    ctx: AuthContext, close_id: UUID, *, issue_class: IssueClass, title: str
) -> UUID:
    """A `close_note`: listed on the Notes tab, never counted."""
    return await create_issue(
        ctx,
        record_type=CLOSE_TARGET,
        record_id=close_id,
        kind="review_point",
        priority="low",
        title=title,
        internal_note=None,
        client_wording=None,
        client_contact_id=None,
        assignee_user_id=None,
        assignee_agent=False,
        blocks=(),
        work_item_id=close_id,
        source=IssueSource(kind="manual", category_path=f"{NOTE_PATH}/{issue_class}"),
    )


# --- the queue -----------------------------------------------------------------------------------


def _class_of(path: str | None) -> tuple[bool, IssueClass | None]:
    """(is a note, its class) for a close issue's category path; (False, None) for another."""
    if not path:
        return False, None
    head, _, tail = path.partition("/")
    if head not in (EXCEPTION_PATH, NOTE_PATH) or tail not in ISSUE_CLASSES:
        return False, None
    return head == NOTE_PATH, tail


def open_exceptions(rows: Sequence[tuple[str | None, str]]) -> int:
    """The Review badge from (category path, status) pairs: open exceptions, notes excluded."""
    count = 0
    for path, status in rows:
        is_note, klass = _class_of(path)
        count += int(status in OPEN_STATUSES and klass is not None and not is_note)
    return count


async def close_issues(
    ctx: AuthContext,
    close_id: UUID,
    *,
    issue_class: str | None = None,
    include_resolved: bool = False,
) -> CloseIssuesOut:
    """CLS-06's queue, facets and badge (US-8.1)."""
    from abacus.modules.closes.service import visible_close

    await visible_close(ctx, close_id)
    page = await list_issues(
        ctx,
        record_type=CLOSE_TARGET,
        record_id=close_id,
        engagement_id=None,
        status=None,
        kind=None,
        limit=1000,
    )
    questions = {q.issue_id: q for q in await questions_for(ctx.tenant, close_id) if q.issue_id}
    by_severity: Counter[str] = Counter()
    notes = 0
    items: list[CloseIssueOut] = []
    for row in page.rows:
        is_note, klass = _class_of(row.category_path)
        if klass is None:
            continue
        if is_note:
            notes += 1
            continue
        is_open = row.status in OPEN_STATUSES
        if is_open:
            by_severity[row.priority] += 1
        if issue_class and klass != issue_class:
            continue
        if not is_open and not include_resolved:
            continue
        account, line = _parse(row.source_ref)
        question = questions.get(row.id)
        items.append(
            CloseIssueOut(
                issue_id=row.id,
                title=await open_text(
                    ctx.tenant, row.title_sealed, ISSUE_SUBJECT, row.id, "title"
                ),
                severity=cast(Severity, row.priority),
                issue_class=klass,
                status=row.status,  # pyright: ignore[reportArgumentType] -- P-04's issue words
                waiting_on_client=question is not None and question.status == "open",
                why_surfaced=(
                    await open_text(
                        ctx.tenant,
                        row.internal_note_sealed,
                        ISSUE_SUBJECT,
                        row.id,
                        "internal_note",
                    )
                    if row.internal_note_sealed
                    else None
                ),
                account_external_id=account,
                register_line_ref=line,
                question_id=question.id if question else None,
            )
        )
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (order[i.severity], str(i.issue_id)))
    return CloseIssuesOut(
        open=sum(by_severity.values()),
        by_severity={s: by_severity.get(s, 0) for s in ("high", "medium", "low")},
        notes=notes,
        items=items,
    )


# --- transaction questions -----------------------------------------------------------------------


async def _question_out(q: QuestionRow) -> TransactionQuestionOut:
    from abacus.modules.closes.service import people

    asked_by = (await people({q.asked_by}))[q.asked_by]
    return TransactionQuestionOut(
        question_id=q.id,
        issue_id=q.issue_id,
        status=q.status,
        asked_by=asked_by,
        asked_at=q.asked_at,
        answered_at=q.answered_at,
    )


async def ask_question(
    ctx: AuthContext, issue_id: UUID, body: TransactionQuestionIn
) -> TransactionQuestionOut:
    """A person sends the firm's template wording about one close issue (US-8.3)."""
    from abacus.modules.closes.service import visible_close

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(SEND, "role")
    row, _, _ = await read_issue(ctx, issue_id)
    is_note, klass = _class_of(row.category_path)
    if row.record_type != CLOSE_TARGET or klass is None or is_note:
        raise NotACloseIssue(ISSUE_SUBJECT)
    close = await visible_close(ctx, row.record_id)
    await authorise(ctx, SEND, await engagement_resource_of(ctx.tenant, close.engagement_id))
    existing = [
        q for q in await questions_for(ctx.tenant, close.work_item_id) if q.issue_id == issue_id
    ]
    if any(q.status == "open" for q in existing):
        return await _question_out(next(q for q in existing if q.status == "open"))
    violations = await check_scope(
        ctx, await get_ref(ctx, close.engagement_id), body.client_wording
    )
    if violations:
        raise OutOfScope(facts={"kinds": ",".join(sorted({v.kind for v in violations}))})
    account, line = _parse(row.source_ref)
    facts = {"issue_class": klass}
    if account:
        facts["account_external_id"] = account
    if line:
        facts["register_line_ref"] = line
    async with tenant_session(ctx.tenant) as session:
        binder = await close_intake_binder(session, close.work_item_id)
    if binder is None:
        raise NoCloseRequests(facts={"close_id": str(close.work_item_id)})
    async with uow(ctx.tenant) as tx:
        await ask_transaction_question(
            tx,
            ctx,
            work_item_id=close.work_item_id,
            request_list_id=binder.id,
            issue_id=issue_id,
            template_id=body.template_id,
            template_version=body.template_version,
            client_wording=body.client_wording,
            context=facts,
            assignee_contact_id=body.assignee_contact_id,
        )
    made = [
        q for q in await questions_for(ctx.tenant, close.work_item_id) if q.issue_id == issue_id
    ]
    return await _question_out(made[-1])
