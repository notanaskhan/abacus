"""TXP-10's read model and actions over C3 issues for an entity return (T-05-T51; TASK-7902; T-05
F8; TXP-10, TXP-00; ADR-005, ADR-052; DEC-4903, DEC-4904). Amber.

Issues are P-04's cross-module primitive (C3); tax never queries `issues` (OWN-001). This module
composes review's own readers into the TXP-10 queue and wraps review's actions with the screen's
rules.

- **Queue.** The return's issues (`review.api.list_issues` on the return), each title opened
  through review (each read logged by P-04). Open issues fall in two sections: **Waiting on the
  client** (sent to the client and not resolved: `issue_awaits_client`) and **Review points**
  (every other open issue). `show_resolved` adds resolved and verified ones (section
  `resolved`). Filters: `section`, `status`, `step` and `q` (a case-insensitive match on the
  opened title). Counts are over the open issues before the filters, so 5 + 6 = 11 equals the
  tab badge and TXP-00's open items (the badge is derived, never stored).
- **Step.** An issue's run step comes from its first linked cell's sheet (`STEP_OF_SHEET`): 01 is
  the TB import, 03 the mapping, 05 and 07 capital and M-2, 06 and 09 the K-1s, and so on
  (DEC-4903). TXP-00 reads `by_step` for its per-step counts.
- **Assignees.** The picker lists the engagement's team (people), the Accrued Agent, and the
  engagement's designated client contacts. A person or the agent is assigned through P-04's
  update; a client contact is reached by sending to the client.
- **Send to the client.** Only the issue's own client wording is sent (P-04's send-to-client:
  one POR-04 request item through `requests.api`, G3 checked); an issue without client wording is
  409 `client_wording_missing`. The internal note never leaves (DEC-4904).
- **Reminder.** A reminder on the issue's request item is a follow-up draft from the firm's
  published C16 Reminder template (`agents.api.draft_follow_ups`), never free text.
- **Resolve.** P-04's resolve, with a note required when no fix was approved for the issue (422
  `resolution_note_required`). The note is sealed under the firm's key beside the issue
  (`tax_issue_resolution_notes`, 0870) and audited with its hash only. A tie-out issue is
  resolved only by the system (P-04's own refusal).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext

TARGET: Final = "tax_return"
Section = Literal["waiting_on_client", "review_points", "resolved"]
SECTIONS: Final[tuple[Section, ...]] = ("waiting_on_client", "review_points")
SECTION_TITLES: Final[Mapping[Section, str]] = {
    "waiting_on_client": "Waiting on the client",
    "review_points": "Review points",
    "resolved": "Resolved",
}
OPEN: Final = frozenset({"open", "in_progress", "reopened"})
DONE: Final = frozenset({"resolved", "verified"})
STEP_OF_SHEET: Final[Mapping[str, str]] = {
    "01": "import_trial_balance",
    "03": "map_lines",
    "02": "depreciation_register",
    "04": "interim_closing_706d",
    "05": "capital_m2",
    "07": "capital_m2",
    "08": "apportionment_ptet",
    "06": "federal_k1s",
    "09": "federal_k1s",
}
AGENT_NAME: Final = "Accrued Agent"
MAX_ISSUES: Final = 500


class ClientWordingMissing(DomainConflict):
    """Only the issue's client wording is ever sent; without one nothing is."""

    code = "client_wording_missing"


class NoRequestItem(DomainConflict):
    """A reminder needs the request item the issue was sent as."""

    code = "issue_not_sent"


class ResolutionNoteRequired(DomainInvalid):
    """Resolving an issue no approved fix closed needs the person's note."""

    code = "resolution_note_required"


@dataclass(frozen=True)
class QueueAssignee:
    kind: Literal["person", "agent"]
    user_id: UUID | None
    name: str


@dataclass(frozen=True)
class QueueIssue:
    id: UUID
    title: str
    section: Section
    step: str | None
    status: str
    kind: str
    priority: str
    source_kind: str | None
    category_path: str | None
    blocks: tuple[str, ...]
    assignee: QueueAssignee | None
    links: tuple[Mapping[str, object], ...]
    request_item_id: UUID | None
    version: int
    created_at: datetime
    allowed_actions: tuple[str, ...]


@dataclass(frozen=True)
class IssueQueue:
    items: list[QueueIssue]
    by_section: dict[str, int]
    by_step: dict[str, int]
    open_total: int
    resolved_total: int
    sections: list[tuple[Section, str, int]] = field(
        default_factory=list[tuple[Section, str, int]]
    )


def step_of(links: Sequence[Mapping[str, object]]) -> str | None:
    """The run step of an issue's first linked cell's sheet (DEC-4903)."""
    for link in links:
        sheet = str(link.get("sheet") or "")
        if not sheet:
            raw = str(link.get("range") or link.get("cell") or "")
            sheet = raw.split("!", 1)[0] if "!" in raw else ""
        if sheet in STEP_OF_SHEET:
            return STEP_OF_SHEET[sheet]
    return None


def section_of(status: str, awaits_client: bool) -> Section:
    if status in DONE:
        return "resolved"
    return "waiting_on_client" if awaits_client else "review_points"


def matches(item: QueueIssue, *, section: str | None, status: str | None, step: str | None,
            q: str | None) -> bool:  # fmt: skip
    if section is not None and item.section != section:
        return False
    if status is not None and item.status != status:
        return False
    if step is not None and item.step != step:
        return False
    return not q or q.casefold().strip() in item.title.casefold()


def counts(items: Sequence[QueueIssue]) -> tuple[dict[str, int], dict[str, int]]:
    """Open issues by section and by step (before any filter)."""
    open_items = [i for i in items if i.status in OPEN]
    by_section = {s: 0 for s in SECTIONS} | dict(Counter(i.section for i in open_items))
    by_step = dict(Counter(i.step for i in open_items if i.step is not None))
    return by_section, by_step


async def _engagement_of(ctx: AuthContext, return_id: UUID) -> UUID:
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
    if found is None:
        raise NotFound(TARGET)
    return UUID(str(found))


async def issue_queue(
    ctx: AuthContext,
    return_id: UUID,
    *,
    section: str | None = None,
    status: str | None = None,
    step: str | None = None,
    q: str | None = None,
    show_resolved: bool = False,
) -> IssueQueue:
    """TXP-10's queue (module docstring). P-04 authorises `issue.read` on the return."""
    from abacus.modules.review.api import issue_awaits_client, issue_links, list_issues, read_issue

    page = await list_issues(
        ctx, record_type=TARGET, record_id=return_id, engagement_id=None, status=None, kind=None,
        limit=MAX_ISSUES,
    )  # fmt: skip
    links = await issue_links(ctx.tenant, [r.id for r in page.rows])
    items: list[QueueIssue] = []
    for row in page.rows:
        if row.status not in OPEN and row.status not in DONE:
            continue  # not applicable: never in the queue
        _, texts, actions = await read_issue(ctx, row.id)
        cells = tuple(ref for kind, ref in links.get(row.id, []) if kind == "cell_range")
        request_item = next(
            (
                UUID(str(ref["id"]))
                for kind, ref in links.get(row.id, [])
                if kind == "request_item"
            ),
            None,
        )
        awaits = row.status in OPEN and await issue_awaits_client(ctx.tenant, row.id)
        assignee = (
            QueueAssignee("agent", None, AGENT_NAME)
            if row.assignee_agent
            else (
                QueueAssignee(
                    "person", row.assignee_user_id, page.names.get(row.assignee_user_id, "")
                )
                if row.assignee_user_id is not None
                else None
            )
        )
        items.append(
            QueueIssue(
                id=row.id, title=texts.title, section=section_of(row.status, awaits),
                step=step_of(cells), status=row.status, kind=row.kind, priority=row.priority,
                source_kind=row.source_kind, category_path=row.category_path, blocks=row.blocks,
                assignee=assignee, links=cells, request_item_id=request_item, version=row.version,
                created_at=row.created_at, allowed_actions=tuple(actions),
            )
        )  # fmt: skip
    by_section, by_step = counts(items)
    shown = [
        i
        for i in items
        if (show_resolved or i.status in OPEN)
        and matches(i, section=section, status=status, step=step, q=q)
    ]
    shown.sort(key=lambda i: (i.section != "waiting_on_client", i.status in DONE, i.created_at))
    resolved_total = sum(1 for i in items if i.status in DONE)
    return IssueQueue(
        items=shown,
        by_section=by_section,
        by_step=by_step,
        open_total=sum(by_section.values()),
        resolved_total=resolved_total,
        sections=[(s, SECTION_TITLES[s], by_section.get(s, 0)) for s in SECTIONS],
    )


# --- the assignee picker ------------------------------------------------------------------------


@dataclass(frozen=True)
class AssigneeOption:
    kind: Literal["person", "agent", "client_contact"]
    id: UUID | None
    name: str
    detail: str | None = None


async def assignee_options(ctx: AuthContext, return_id: UUID) -> list[AssigneeOption]:
    """The team (people), the Accrued Agent, and the engagement's designated client contacts.
    The caller authorised `issue.read` on the return."""
    from abacus.modules.engagements.api import (
        client_contact_names,
        engagement_contacts,
        engagement_roster,
    )

    engagement_id = await _engagement_of(ctx, return_id)
    people = await engagement_roster(ctx, engagement_id)
    designations = await engagement_contacts(ctx, engagement_id)
    names = await client_contact_names(
        ctx.tenant, engagement_id, [d.contact_id for d in designations]
    )
    out = [AssigneeOption("person", m.user_id, m.display_name, m.role) for m in people]
    out.append(AssigneeOption("agent", None, AGENT_NAME))
    seen: set[UUID] = set()
    for d in designations:
        if d.contact_id in names and d.contact_id not in seen:
            seen.add(d.contact_id)
            out.append(AssigneeOption("client_contact", d.contact_id, names[d.contact_id]))
    return out


# --- actions ------------------------------------------------------------------------------------


async def _on_return(ctx: AuthContext, return_id: UUID, issue_id: UUID) -> None:
    """The issue is this return's (another record's issue answers 404 here)."""
    from abacus.modules.review.api import issue_row

    row = await issue_row(ctx.tenant, issue_id)
    if row.record_type != TARGET or row.record_id != return_id:
        raise NotFound("issue")


async def send_to_client(
    ctx: AuthContext,
    return_id: UUID,
    issue_id: UUID,
    *,
    seen_version: int,
    contact_id: UUID,
    due_on: date | None,
) -> UUID:
    """Only the issue's client wording goes, through P-04's send (DEC-4904)."""
    from abacus.modules.review.api import read_issue, send_issue_to_client

    await _on_return(ctx, return_id, issue_id)
    _, texts, _ = await read_issue(ctx, issue_id)
    wording = (texts.client_wording or "").strip()
    if not wording:
        raise ClientWordingMissing(facts={"issue_id": str(issue_id)})
    return await send_issue_to_client(
        ctx, issue_id, seen_version=seen_version, client_wording=wording, contact_id=contact_id,
        due_on=due_on,
    )  # fmt: skip


async def remind(ctx: AuthContext, return_id: UUID, issue_id: UUID) -> int:
    """A follow-up draft from the C16 Reminder template on the issue's request item."""
    from abacus.modules.agents.api import draft_follow_ups
    from abacus.modules.review.api import issue_links, read_issue

    await _on_return(ctx, return_id, issue_id)
    await read_issue(ctx, issue_id)  # `issue.read` on the return, as P-04 checks it
    found = (await issue_links(ctx.tenant, [issue_id])).get(issue_id, [])
    items = [UUID(str(ref["id"])) for kind, ref in found if kind == "request_item"]
    if not items:
        raise NoRequestItem(facts={"issue_id": str(issue_id)})
    drafts = await draft_follow_ups(ctx, [], items[-1:])
    return len(drafts)


_NOTE: Final = text(
    "INSERT INTO tax_issue_resolution_notes (tenant_id, engagement_id, work_item_id, issue_id, "
    "note_sealed, note_sha256, created_by) VALUES (:t, :e, :w, :i, :sealed, :sha, :by)"
)


async def fix_approved(ctx: AuthContext, issue_id: UUID) -> bool:
    """Whether the issue's latest fix proposal was approved by a person."""
    from abacus.modules.agents.api import proposal_approver
    from abacus.modules.review.api import issue_run_facts

    _, run, _ = await issue_run_facts(ctx.tenant, issue_id)
    if run is None or run.proposal_id is None:
        return False
    async with tenant_session(ctx.tenant) as session:
        return await proposal_approver(session, run.proposal_id) is not None


async def resolve(
    ctx: AuthContext, return_id: UUID, issue_id: UUID, *, seen_version: int, note: str | None
) -> None:
    """P-04's resolve, with the note rule (module docstring)."""
    from abacus.kernel.crypto import seal
    from abacus.modules.review.api import move_issue

    await _on_return(ctx, return_id, issue_id)
    text_note = (note or "").strip()
    if not text_note and not await fix_approved(ctx, issue_id):
        raise ResolutionNoteRequired(facts={"issue_id": str(issue_id)})
    await move_issue(ctx, issue_id, "resolved", seen_version)
    if not text_note:
        return
    engagement_id = await _engagement_of(ctx, return_id)
    sealed = await seal(
        ctx.tenant_id,
        text_note.encode(),
        hashlib.sha256(f"tax_issue_resolution_note:{issue_id}".encode()).hexdigest(),
    )
    sha = hashlib.sha256(text_note.encode()).hexdigest()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _NOTE,
            {"t": ctx.tenant_id, "e": engagement_id, "w": return_id, "i": issue_id,
             "sealed": sealed, "sha": sha, "by": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "issue.resolution_noted",
            target=Target("issue", issue_id),
            after=Ref(note_sha256=sha),
            scope=Scope(engagement_id=engagement_id),
        )


__all__ = [
    "AGENT_NAME",
    "SECTIONS",
    "SECTION_TITLES",
    "STEP_OF_SHEET",
    "AssigneeOption",
    "ClientWordingMissing",
    "IssueQueue",
    "NoRequestItem",
    "QueueAssignee",
    "QueueIssue",
    "ResolutionNoteRequired",
    "assignee_options",
    "counts",
    "fix_approved",
    "issue_queue",
    "matches",
    "remind",
    "resolve",
    "section_of",
    "send_to_client",
    "step_of",
]
