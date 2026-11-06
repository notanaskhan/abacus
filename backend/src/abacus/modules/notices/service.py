"""The notices core (N-04-T06; N-04 §3 F1 to F3, §4.2, §4.3; NOT-01, NOT-02; DEC-2210).

- **Status machine.** `notices.status` moves only along `TRANSITIONS`, each move written with its
  `notice_status_events` row in the same unit of work; anything else answers 409
  `illegal_transition` with the from and to codes as facts. Received → Classified is a person's
  Start; the analysis, the decision, the send and the agency's reply move the rest (N-04-T11
  onward). `closed` is terminal.
- **Index and tallies.** Rows by deadline risk: open notices by respond-by ascending (red within
  7 days, amber within 30), then sent and awaiting rows, then closed. Tiles by QN-6 (New =
  received; Analyzing = classified + analyzing; Response drafted = response_drafted + approved;
  Awaiting = sent + awaiting_irs; escalated rows count as open and have no tile). Every count is
  from the viewer's visible rows (`visible()`, DEC-43), so a walled notice leaves the tallies as
  well as the list.
- **Edits** (`notice.assign`, `notice.update`): against the row's version (409
  `version_conflict`); a respond-by a person corrects is `corrected`. Audited.
- **HOME-01** reads the same rows through `platform.register_home_count('notices')`.

The routes have authorised their action on the notice's engagement and the flag.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import column, select, table, text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, names_of, visible

OPEN: Final = frozenset(
    {"received", "classified", "analyzing", "response_drafted", "approved", "escalated"}
)
TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "received": frozenset({"classified", "closed"}),
    "classified": frozenset({"analyzing", "response_drafted", "closed", "escalated"}),
    "analyzing": frozenset({"response_drafted", "classified", "escalated"}),
    "response_drafted": frozenset({"approved", "analyzing", "escalated"}),
    "approved": frozenset({"sent", "response_drafted"}),
    "sent": frozenset({"awaiting_irs", "closed", "escalated"}),
    "awaiting_irs": frozenset({"closed", "escalated"}),
    "escalated": frozenset({"classified", "analyzing", "response_drafted", "closed"}),
    "closed": frozenset(),
}
TILES: Final[dict[str, str]] = {
    "received": "new",
    "classified": "analyzing",
    "analyzing": "analyzing",
    "response_drafted": "response_drafted",
    "approved": "response_drafted",
    "sent": "awaiting",
    "awaiting_irs": "awaiting",
}
_ORDER: Final[dict[str, int]] = {"open": 0, "awaiting": 1, "closed": 2}
_AUTH_LABEL: Final[dict[str, str]] = {
    "form_8821": "8821 ✓",
    "form_2848": "2848 ✓",
    "state_poa": "POA ✓",
    "none": "None · blocked",
}


class IllegalTransition(DomainConflict):
    code = "illegal_transition"


class VersionConflict(DomainConflict):
    code = "version_conflict"


@dataclass(frozen=True)
class Notice:
    id: UUID
    engagement_id: UUID
    client_entity_id: UUID | None
    agency: str | None
    agency_name: str | None
    notice_type_key: str | None
    notice_code: str
    title: str | None
    tax_year: int | None
    form: str | None
    received_on: date
    notice_date: date | None
    respond_by: date | None
    respond_by_source: str | None
    amount_tax: Decimal | None
    amount_interest: Decimal | None
    amount_penalty: Decimal | None
    amount_total: Decimal | None
    interest_to: date | None
    taxpayer_tin_last4: str | None
    related_return_id: UUID | None
    authorization_kind: str
    authorization_id: UUID | None
    status: str
    position: str | None
    decision_id: UUID | None
    decided_at: datetime | None
    partner_owned: bool
    follow_up_on: date | None
    closed_on: date | None
    escalated_reason: str | None
    client_visible: bool
    assignee_user_id: UUID | None
    status_changed_at: datetime
    row_version: int

    @property
    def tile(self) -> str | None:
        return TILES.get(self.status)

    @property
    def open(self) -> bool:
        return self.status in OPEN

    @property
    def can_represent(self) -> bool:
        return self.authorization_kind in ("form_2848", "state_poa")

    @property
    def authorization_label(self) -> str:
        return _AUTH_LABEL[self.authorization_kind]


@dataclass(frozen=True)
class NoticeTallies:
    tiles: dict[str, int]
    by_type: dict[str, int]
    open: int
    due_within_7: int
    blocked: int


_COLUMNS: Final = (
    "work_item_id AS id, engagement_id, client_entity_id, agency, agency_name, notice_type_key, "
    "notice_code, title, tax_year, form, received_on, notice_date, respond_by, "
    "respond_by_source, amount_tax, amount_interest, amount_penalty, amount_total, interest_to, "
    "taxpayer_tin_last4, related_return_id, authorization_kind, authorization_id, status, "
    "position, decision_id, decided_at, partner_owned, follow_up_on, closed_on, "
    "escalated_reason, client_visible, assignee_user_id, status_changed_at, row_version"
)


def _notice(row: object) -> Notice:
    r = dict(cast(dict[str, object], row))
    r["tax_year"] = None if r["tax_year"] is None else int(cast(int, r["tax_year"]))
    return Notice(**r)  # pyright: ignore[reportArgumentType] -- the columns are the fields


def risk_band(respond_by: date | None, on: date, status: str) -> str:
    """Red within 7 days, amber within 30, otherwise none; only an open notice is at risk."""
    if respond_by is None or status not in OPEN:
        return "none"
    days = (respond_by - on).days
    return "red" if days <= 7 else "amber" if days <= 30 else "none"


def _sort_key(n: Notice) -> tuple[int, date, str]:
    group = "open" if n.open else "closed" if n.status == "closed" else "awaiting"
    return (_ORDER[group], n.respond_by or date.max, str(n.id))


_FIELDS: Final = tuple(f.strip() for f in _COLUMNS.split(","))
_NAMES: Final = tuple(f.split(" AS ")[0] for f in _FIELDS)
_TABLE: Final = table("notices", *(column(n, type_=None) for n in _NAMES))  # pyright: ignore[reportUnknownArgumentType] -- SQLAlchemy's column() is untyped


async def visible_notices(ctx: AuthContext) -> list[Notice]:
    """The notices on the engagements the viewer may read (`notice.read`), walls applied."""
    query = select(*(_TABLE.c[n].label("id" if n == "work_item_id" else n) for n in _NAMES)).where(
        visible(ctx, "notice.read", _TABLE.c.engagement_id)
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(query)).mappings().all()
    return sorted((_notice(r) for r in rows), key=_sort_key)


def tallies(rows: Sequence[Notice], on: date) -> NoticeTallies:
    """NOT-01's tiles and summary line from the rows the viewer sees (DEC-43)."""
    opened = [n for n in rows if n.open]
    tiles = Counter(n.tile for n in rows if n.tile is not None)
    by_type = Counter(
        ("state" if n.agency == "state" else (n.notice_type_key or "unknown")) for n in opened
    )
    return NoticeTallies(
        tiles={k: tiles.get(k, 0) for k in ("new", "analyzing", "response_drafted", "awaiting")},
        by_type=dict(by_type),
        open=len(opened),
        due_within_7=sum(1 for n in opened if risk_band(n.respond_by, on, n.status) == "red"),
        blocked=sum(1 for n in opened if n.authorization_kind == "none"),
    )


async def notice_for_run(tenant: TenantContext, notice_id: UUID) -> Notice | None:
    """One notice for a run a person already started on it: tenant-scoped, no viewer (the start
    authorised `notice.analyze`, and read it through `visible`)."""
    query = select(*(_TABLE.c[n].label("id" if n == "work_item_id" else n) for n in _NAMES)).where(
        _TABLE.c.work_item_id == notice_id
    )
    async with tenant_session(tenant) as session:
        row = (await session.execute(query)).mappings().first()
    return None if row is None else _notice(row)


async def notice(ctx: AuthContext, notice_id: UUID) -> Notice:
    """One notice the viewer may read; walled or unknown: 404 (never a hint it exists)."""
    for found in await visible_notices(ctx):
        if found.id == notice_id:
            return found
    raise NotFound("notice")


async def names(user_ids: Sequence[UUID | None]) -> dict[UUID, str]:
    wanted = sorted({u for u in user_ids if u is not None}, key=str)
    return await names_of(wanted) if wanted else {}


async def move(
    tx: UnitOfWork,
    found: Notice,
    to: str,
    *,
    actor_kind: str,
    actor_user_id: UUID | None,
    reason_code: str | None = None,
) -> None:
    """The one status move, with its event row; 409 `illegal_transition` otherwise."""
    if to not in TRANSITIONS.get(found.status, frozenset()):
        raise IllegalTransition(facts={"from_status": found.status, "to_status": to})
    moved = await tx.session.scalar(
        text(
            "UPDATE notices SET status = :to, status_changed_at = abacus_now(), "
            "row_version = row_version + 1 WHERE work_item_id = :id AND status = :from "
            "RETURNING work_item_id"
        ),
        {"to": to, "id": found.id, "from": found.status},
    )
    if moved is None:
        raise VersionConflict
    await tx.session.execute(
        text(
            "INSERT INTO notice_status_events (tenant_id, work_item_id, from_status, to_status, "
            "actor_kind, actor_user_id, reason_code) SELECT tenant_id, work_item_id, :from, :to, "
            ":kind, :by, :reason FROM notices WHERE work_item_id = :id"
        ),
        {
            "from": found.status,
            "to": to,
            "kind": actor_kind,
            "by": actor_user_id,
            "reason": reason_code,
            "id": found.id,
        },
    )
    tx.record(
        "notice.status_changed",
        target=Target("notice", found.id),
        after=Ref(version=found.row_version + 1),
    )


async def start(ctx: AuthContext, notice_id: UUID, expected_version: int | None) -> Notice:
    """A person's Start: Received → Classified (N-04 F2)."""
    found = await notice(ctx, notice_id)
    if expected_version is not None and expected_version != found.row_version:
        raise VersionConflict
    async with uow(ctx.tenant) as tx:
        await move(tx, found, "classified", actor_kind="human", actor_user_id=ctx.user_id)
    return await notice(ctx, notice_id)


async def edit(
    ctx: AuthContext,
    notice_id: UUID,
    expected_version: int,
    *,
    assignee_id: UUID | None = None,
    respond_by: date | None = None,
    related_return_id: UUID | None = None,
    client_visible: bool | None = None,
) -> Notice:
    """Assign, correct the respond-by, link the return or share with the client."""
    found = await notice(ctx, notice_id)
    if found.row_version != expected_version:
        raise VersionConflict
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE notices SET assignee_user_id = coalesce(:assignee, assignee_user_id), "
                "respond_by = coalesce(:respond_by, respond_by), "
                "respond_by_source = CASE WHEN :respond_by IS NULL THEN respond_by_source "
                "ELSE 'corrected' END, "
                "related_return_id = coalesce(:related, related_return_id), "
                "client_visible = coalesce(:visible, client_visible), "
                "row_version = row_version + 1 WHERE work_item_id = :id AND row_version = :v "
                "RETURNING work_item_id"
            ),
            {
                "assignee": assignee_id,
                "respond_by": respond_by,
                "related": related_return_id,
                "visible": client_visible,
                "id": notice_id,
                "v": expected_version,
            },
        )
        if moved is None:
            raise VersionConflict
        action = "notice.assigned" if assignee_id is not None else "notice.updated"
        tx.record(
            action, target=Target("notice", notice_id), after=Ref(version=expected_version + 1)
        )
    return await notice(ctx, notice_id)


async def audit_events(ctx: AuthContext, notice_id: UUID) -> list[tuple[datetime, str, str]]:
    """NOT-02 a2's activity: the notice's audit events, newest first (after the read check)."""
    # audit_trail is an edge module: its reader reaches notices through identity's slot (ADR-008).
    from abacus.modules.identity.api import target_events

    await notice(ctx, notice_id)
    rows = await target_events(ctx.tenant, "notice", notice_id, None, 100)
    return [(r.occurred_at, r.action, r.actor_kind) for r in rows]


async def status_of(tenant: TenantContext, work_item_id: UUID) -> str:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT status FROM notices WHERE work_item_id = :id"), {"id": work_item_id}
        )
    return cast(str | None, found) or "received"


async def on_day(ctx: AuthContext) -> date:
    return await today(ctx.tenant)


async def notice_document_versions(tenant: TenantContext, notice_id: UUID) -> list[UUID]:
    """The notice's files, oldest first: the letter it was opened from, then what was attached to
    it (the 1099s filed to it, INB-02 d). N-04-T11's word-layer search reads them in order."""
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT evidence_version_id FROM notice_intakes "
                "WHERE created_work_item_id = :w AND evidence_version_id IS NOT NULL "
                "ORDER BY created_at, id"
            ),
            {"w": notice_id},
        )
        return [UUID(str(version)) for version in found.scalars()]
