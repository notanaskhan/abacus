"""AUD-29 · the engagement activity log (P-05-T11; SPEC-650 AC-31 to AC-38; P-05 §4.3).

The engagement's audit events, read through ADM-07's explorer (`explorer.shown_to`, labels,
`row_of`) narrowed to one engagement, so walls, `visible()` and the catalogue's INV-1 marker rule
are the explorer's own, never re-implemented here.

- **Segments** (AC-32): `via_agent` is actor kind `agent`, or `system` with an agent run in its
  references; `policy` is actor kind `policy`; everything else (people, client and third-party
  principals, gate facts, support) is `human`. `counts` {all, human, via_agent, policy} come
  from the same filter without the segment, so they foot under every Type, Date or search filter.
- **The Activity catalogue** (P-05 §4.3): each action's deep-link kind, search keywords and
  whether the default list shows it. Collaboration events stay out except a to-do's deletion and
  a comment's redaction (P-05 OQ-4); an action with no entry appears under its catalogue
  category with the generic grammar. Modules add their own through `register_activity_links`
  (their `ACTIVITY_KINDS`), so no later epic edits this file.
- **Order and paging:** newest first by business time (`effective_at`), keyset on `(effective_at,
  seq)`.
- **Search** (AC-34): the label index (`labels.matching`: actor name, resolved target label,
  detail facts, keywords) as a predicate inside the query, inside the engagement and the window;
  the text arrives in the body and is never logged.
- **Export** (AC-38): the same filter as CSV, streamed from pages of the explorer's rows, every
  cell neutralised against formula injection (`exports._cell`), no values column (masked as on
  screen; never a Restricted value, DEC-60), at most `EXPORT_CAP` rows; `audit_event.exported`
  records the filter's fingerprint and the row count on the engagement.
- **INV-1** (AC-33): a decision-class (`ok`-marked) action carrying actor kind `agent` is logged
  as `activity.inv1_agent_decision` (action code and seq only) and shown with the neutral marker;
  `tests/unit/audit_trail/test_p05t11_engagement_activity.py` fails the build on any catalogue
  entry that would allow it.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, case, distinct, func, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.listing import (
    TOTAL_CAP,
    ListPage,
    Position,
    capped_total,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.audit_trail import explorer
from abacus.modules.audit_trail import labels as label_index
from abacus.modules.audit_trail.activity_catalogue import activity_of
from abacus.modules.audit_trail.audit_log_contract import AuditEventRow, LinkKind
from abacus.modules.audit_trail.exports import CSV_COLUMNS, _cell, _json_cell
from abacus.modules.identity.api import AuthContext

Segment = Literal["all", "human", "via_agent", "policy"]
SEGMENTS: Final = ("human", "via_agent", "policy")
RESOURCE: Final = "engagement_audit_events"
EXPORT_CAP: Final = 10_000
EXPORT_PAGE: Final = 500
_log = get_logger(__name__)

t = explorer.t


@dataclass(frozen=True)
class ActivityLink:
    """How AUD-29 shows an action: where its row's click goes, the words it is found by, and
    whether the default list shows it."""

    link_kind: LinkKind = "none"
    search_keywords: tuple[str, ...] = ()
    in_activity: bool = True


def _link(kind: LinkKind, *keywords: str, shown: bool = True) -> ActivityLink:
    return ActivityLink(kind, keywords, shown)


# The v1 entries for the actions AUD-29a renders by S35 (P-05 §4.3). Prefix entries (ending in
# ".") apply to every action of the entity; an exact entry wins over a prefix.
ACTIVITY_LINKS: Final[Mapping[str, ActivityLink]] = {
    # Runs, drafts and resumes open the WB-09 run trace.
    "agent_run.": _link("run", "run", "agent"),
    "engagement_run.": _link("run", "run", "agent"),
    "draft.": _link("run", "draft"),
    # Sign-offs open AUD-06 with the signed cells lit.
    "sign_off.": _link("sign_off", "sign-off", "signed"),
    "signoff.": _link("sign_off", "sign-off", "signed"),
    # Materiality opens AUD-07 at that version.
    "materiality.": _link("materiality", "materiality"),
    # Documents open AUD-03 with the file in the viewer.
    "document.": _link("document", "document"),
    "evidence.": _link("document", "document", "evidence"),
    "upload.": _link("document", "document", "upload"),
    # Risks open the AUD-08 drawer at that version.
    "risk.": _link("risk", "risk"),
    "risk_assessment.": _link("risk", "risk"),
    # Gates G1 to G4 open ENG-02 or CLI-07.
    "gate.": _link("gate", "gate"),
    "acceptance.": _link("gate", "acceptance", "gate"),
    "independence.": _link("gate", "independence", "gate"),
    "decision.": _link("none", "decision"),
    "request_list.": _link("none", "request list"),
    "version.": _link("none", "version"),
    # Collaboration stays out of the default list except deletions and redactions (OQ-4).
    "comment.": _link("none", shown=False),
    "comment_thread.": _link("none", shown=False),
    "todo.": _link("todo", "to-do", shown=False),
    "todo.deleted": _link("todo", "to-do", "deleted"),
    "comment.redacted": _link("none", "comment", "redacted"),
    # The export itself (category Exports).
    "audit_event.exported": _link("none", "export", "download"),
}

_REGISTERED: dict[str, ActivityLink] = {}


def register_activity_links(links: Mapping[str, ActivityLink]) -> None:
    """A module's own AUD-29 entries (`ACTIVITY_KINDS`); an action or prefix has one entry."""
    for action, link in links.items():
        known = ACTIVITY_LINKS.get(action) or _REGISTERED.get(action)
        if known is not None and known != link:
            raise ValueError(f"activity entry {action!r} already exists")
        _REGISTERED[action] = link


def activity_kinds() -> dict[str, ActivityLink]:
    """Every entry, static and registered (the generated catalogue's view)."""
    return {**_REGISTERED, **ACTIVITY_LINKS}


def link_of(action: str) -> ActivityLink:
    kinds = activity_kinds()
    exact = kinds.get(action)
    if exact is not None:
        return exact
    entity, _, _ = action.partition(".")
    return kinds.get(f"{entity}.", ActivityLink())


def _hidden_actions() -> tuple[list[str], list[str]]:
    """The exact actions and the entity prefixes the default list leaves out."""
    exact: list[str] = []
    prefixes: list[str] = []
    for key, link in sorted(activity_kinds().items()):
        if link.in_activity:
            continue
        (prefixes if key.endswith(".") else exact).append(key)
    return exact, prefixes


def _shown_actions() -> list[str]:
    """Exact entries shown although their prefix is hidden (`todo.deleted`)."""
    kinds = activity_kinds()
    return sorted(
        key
        for key, link in kinds.items()
        if link.in_activity
        and not key.endswith(".")
        and not kinds.get(key.partition(".")[0] + ".", ActivityLink()).in_activity
    )


def in_activity_list() -> ColumnElement[bool]:
    """The default list's actions, in SQL: hidden prefixes and exact entries out, their shown
    exceptions back in."""
    exact, prefixes = _hidden_actions()
    hidden = [t.action.in_(exact)] if exact else []
    hidden += [t.action.startswith(prefix) for prefix in prefixes]
    if not hidden:
        return literal(True)
    shown = _shown_actions()
    keep = t.action.in_(shown) if shown else literal(False)
    return or_(keep, ~or_(*hidden))


# AC-32: the segment of an event, in SQL. A system event with an agent run in its references
# reads "via Agent" (the run acted for a person); support, client and gate facts read Human.
_HAS_RUN: Final = or_(
    t.after_ref["run_id"].astext.is_not(None),
    t.after_ref["agent_run_id"].astext.is_not(None),
)
SEGMENT: Final[ColumnElement[str]] = case(
    (t.actor_kind == "agent", literal("via_agent")),
    (and_(t.actor_kind == "system", _HAS_RUN), literal("via_agent")),
    (t.actor_kind == "policy", literal("policy")),
    else_=literal("human"),
)


@dataclass(frozen=True)
class ActivityFilter:
    engagement_id: UUID
    segment: Segment = "all"
    categories: tuple[str, ...] = ()
    since: datetime | None = None
    until: datetime | None = None
    q: str | None = None

    def digest(self) -> str:
        return query_hash(
            engagement=self.engagement_id,
            segment=self.segment,
            categories=sorted(self.categories),
            since=self.since,
            until=self.until,
            q=self.q,
        )

    def fingerprint(self) -> str:
        """The filter's SHA-256 (a `Ref` may hold a fingerprint, never the search text)."""
        canonical = json.dumps(
            {
                "engagement": str(self.engagement_id),
                "segment": self.segment,
                "categories": sorted(self.categories),
                "since": self.since.isoformat() if self.since else None,
                "until": self.until.isoformat() if self.until else None,
                "q": self.q,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


async def _actions_in(
    ctx: AuthContext, engagement_id: UUID, categories: tuple[str, ...]
) -> list[str]:
    """The engagement's actions whose catalogue category is one of `categories`. The catalogue
    is code, so the category filter is the set of the engagement's distinct actions it places
    there (one indexed read)."""
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            select(distinct(t.action)).where(explorer.ENGAGEMENT == engagement_id)
        )
        actions = [str(a) for a in found.scalars().all()]
    wanted = frozenset(categories)
    return sorted(a for a in actions if activity_of(a).category in wanted)


async def _conditions(
    ctx: AuthContext, reader: explorer.Reader, where: ActivityFilter
) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = [
        explorer.shown_to(reader),
        explorer.ENGAGEMENT == where.engagement_id,
        in_activity_list(),
    ]
    if where.categories:
        found.append(t.action.in_(await _actions_in(ctx, where.engagement_id, where.categories)))
    if where.since is not None:
        found.append(t.effective_at >= where.since)
    if where.until is not None:
        found.append(t.effective_at < where.until)
    if where.q is not None:
        await label_index.catch_up(ctx.tenant_id)
        found.append(label_index.matching(t.seq, where.q))
    return found


async def _counts(db: AsyncSession, conditions: list[ColumnElement[bool]]) -> dict[str, int]:
    """`all` and each segment over the other filters, capped like `total`."""
    sub = (
        select(SEGMENT.label("segment"))
        .where(and_(true(), *conditions))
        .limit(TOTAL_CAP + 1)
        .subquery()
    )
    grouped = await db.execute(select(sub.c.segment, func.count()).group_by(sub.c.segment))
    by_segment = {str(kind): int(n) for kind, n in grouped.all()}
    counts = {kind: min(by_segment.get(kind, 0), TOTAL_CAP) for kind in SEGMENTS}
    counts["all"] = min(sum(by_segment.values()), TOTAL_CAP)
    return {"all": counts["all"], **{k: counts[k] for k in SEGMENTS}}


def _row(row: Mapping[str, object], reader: explorer.Reader, found: object) -> AuditEventRow:
    """The explorer's row with AUD-29's link kind; INV-1 logged if a decision names the agent."""
    out = explorer.row_of(dict(row), reader, cast(explorer._Labels, found))  # pyright: ignore[reportPrivateUsage] - the explorer's label bundle
    if str(row["actor_kind"]) == "agent" and activity_of(out.action).mark == "ok":
        _log.error("activity.inv1_agent_decision", action=out.action, seq=out.seq)
    link = link_of(out.action)
    kind: LinkKind = "run" if out.run_id is not None else link.link_kind
    return out.model_copy(update={"link_kind": kind})


async def query(
    ctx: AuthContext, where: ActivityFilter, cursor: str | None, limit: int
) -> ListPage[AuditEventRow]:
    """AC-31, AC-32, AC-34: one page, newest first, with the four counts. The route checked the
    principal, the engagement, the action and the flag."""
    reader = await explorer.reader_of(ctx)
    digest = where.digest()
    after: Position | None = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=digest)
        if cursor
        else None
    )
    others = await _conditions(ctx, reader, where)
    conditions = list(others)
    if where.segment != "all":
        conditions.append(SEGMENT == where.segment)
    async with tenant_session(ctx.tenant) as session:
        stmt = keyset(
            explorer._select(conditions),  # pyright: ignore[reportPrivateUsage] - the explorer's wide row
            sort=cast(ColumnElement[object], t.effective_at),
            id_column=cast(ColumnElement[object], t.seq),
            after=after,
            descending=True,
            limit=limit,
        )
        fetched = [dict(m) for m in (await session.execute(stmt)).mappings().all()]
        total = await capped_total(session, explorer._select(conditions))  # pyright: ignore[reportPrivateUsage] - as above
        counts = await _counts(session, others)
    rows, next_position = page_of(
        fetched, limit=limit, key=lambda r: r["effective_at"], id_of=lambda r: r["seq"]
    )
    found = await explorer._labels(ctx, rows)  # pyright: ignore[reportPrivateUsage] - names and target labels
    return envelope(
        [_row(r, reader, found) for r in rows],
        next_position=next_position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=digest,
        total=total,
        counts=counts,
    )


EXPORT_COLUMNS: Final = (*CSV_COLUMNS, "link_kind")


def _csv_cells(row: AuditEventRow) -> list[str]:
    actor = row.actor
    cells: list[object] = [
        row.seq,
        row.effective_at.isoformat(),
        row.action,
        row.category,
        actor.kind,
        actor.person.user_id if actor.person else None,
        actor.person.display_name if actor.person else None,
        actor.on_behalf_of.user_id if actor.on_behalf_of else None,
        actor.on_behalf_of.display_name if actor.on_behalf_of else None,
        actor.agent_id,
        actor.policy_ref,
        row.target.type,
        row.target.id,
        row.target.label,
        row.target.engagement_id,
        row.target.client_id,
        row.office_id,
        row.ip,
    ]
    out = [_cell(c) for c in cells]
    out.append(_json_cell(row.detail_facts))
    out.append(_cell(row.link_kind))
    return out


@dataclass(frozen=True)
class ActivityExport:
    content: bytes
    rows: int
    filename: str


async def export_csv(ctx: AuthContext, where: ActivityFilter) -> ActivityExport:
    """AC-38: the filtered rows (segment included) as CSV, oldest page last like the screen
    (newest first), audited as `audit_event.exported` on the engagement."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    rows = 0
    async for row in _all_rows(ctx, where):
        writer.writerow(_csv_cells(row))
        rows += 1
    async with uow(ctx.tenant) as tx:
        tx.record(
            "audit_event.exported",
            target=Target("engagement", where.engagement_id),
            after=Ref(filter_sha256=where.fingerprint(), row_count=rows),
        )
    return ActivityExport(
        buffer.getvalue().encode("utf-8"), rows, f"engagement-activity-{where.engagement_id}.csv"
    )


async def _all_rows(ctx: AuthContext, where: ActivityFilter) -> AsyncIterator[AuditEventRow]:
    cursor: str | None = None
    seen = 0
    while seen < EXPORT_CAP:
        page = await query(ctx, where, cursor, min(100, EXPORT_CAP - seen))
        for item in page.items:
            yield item
            seen += 1
        cursor = page.next_cursor
        if cursor is None:
            return


__all__ = [
    "ACTIVITY_LINKS",
    "EXPORT_CAP",
    "SEGMENT",
    "ActivityExport",
    "ActivityFilter",
    "ActivityLink",
    "activity_kinds",
    "export_csv",
    "in_activity_list",
    "link_of",
    "query",
    "register_activity_links",
]
