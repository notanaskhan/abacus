"""HOME-01 without the queue, live (I-01-T10; I-01 F4, F5; `home-and-gates.md` §3; DEC-648).

- **Tiles** come from their owners through `platform.register_home_count`, already under
  `visible()`; the set is shaped by the viewer's role: a metadata-only firm role (firm or
  security admin, ADR-024, DEC-20) gets the admin set, everyone else the practice set. A tile
  whose owner has not registered, or whose provider fails, is absent, never zero.
- **Your work** (AC4.2) and **deadlines** (AC4.1) read the viewer's assigned work items
  (`engagements.api.assigned_work`); a metadata-only role has no work band. Deadlines are the
  next 14 days on `kernel.clock` (overdue included), `next` the first one past the window; risk is
  a `due_risk` code computed here.
- **Running count**: the registered `agent_runs_running` count, else null.
- `office_id` narrows every tile, the band and the deadlines (DEC-30); walls leave a client out of
  all of them with nothing counted for it (DEC-43). Client activity is `activity.py` (I-01-T12).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal
from uuid import UUID

from abacus.kernel import clock
from abacus.modules.engagements.api import AssignedWork, assigned_work
from abacus.modules.identity.api import AuthContext, metadata_only, names_of
from abacus.modules.organisations.api import firm_names
from abacus.modules.platform.api import HomeCount, home_count

DueRisk = Literal["overdue", "due_soon", "approaching", "later"]
WINDOW: Final = 14  # days (AC4.1)
SOON: Final = 7  # red ink within 7 days (`due_risk` due_soon)


@dataclass(frozen=True)
class TileSpec:
    key: str
    target: str


# I-01 §2 HOME-01 a (Daniel) and e (Grace): each present once its owner registers.
PRACTICE_TILES: Final = (
    TileSpec("returns", "/tax"),
    TileSpec("audits", "/audits"),
    TileSpec("closes", "/closes"),
    TileSpec("notices", "/notices"),
)
ADMIN_TILES: Final = (
    TileSpec("signatures_out", "/signatures"),
    TileSpec("inbox_waiting", "/inbox"),
    TileSpec("portal_invites_pending", "/clients"),
    TileSpec("binders", "/binders"),
)


@dataclass(frozen=True)
class Tile:
    spec: TileSpec
    count: HomeCount


@dataclass(frozen=True)
class WorkRow:
    work: AssignedWork
    client: str


@dataclass(frozen=True)
class DeadlineRow:
    work_item_id: UUID  # the work item, or the deadline itself when it has none
    due_on: date
    client: str
    filing_label: str
    status: str
    risk: DueRisk
    kind: str | None
    deadline_id: UUID | None = None  # T-08-T20: the `filing_deadlines` row it reads


@dataclass(frozen=True)
class HomeView:
    first_name: str
    today: date
    tiles: list[Tile]
    work_label: str | None  # None: the role has no work band
    work: list[WorkRow]
    deadlines: list[DeadlineRow]
    next_deadline: DeadlineRow | None
    running_count: int | None


def risk_of(due_on: date, today: date) -> DueRisk:
    days = (due_on - today).days
    if days < 0:
        return "overdue"
    if days <= SOON:
        return "due_soon"
    return "approaching" if days <= WINDOW else "later"


def work_label(rows: list[AssignedWork]) -> str:
    """AC4.2: "Your returns" when every item is a tax return, "Your engagements" when every one
    is assurance work, "My work" otherwise (and when there is none)."""
    kinds = {r.kind for r in rows}
    if kinds == {"tax_return"}:
        return "home.your_work.returns"
    if kinds == {"assurance"}:
        return "home.your_work.engagements"
    return "home.your_work.mine"


# HOME-01 opens a filing deadline's own screen: a return and a close by their work item, a notice
# on NOT-02 (N-04-T22's kind), the rest on HOME-03.
_KIND_OF_SOURCE: Final[dict[str, str]] = {
    "tax_return": "tax_return", "extension": "tax_return", "fiduciary_statement": "tax_return",
    "election_window": "tax_return", "close": "close", "notice_response": "notice",
    "form_5500": "assurance", "assurance_report": "assurance",
}  # fmt: skip


async def _filing_deadlines(
    ctx: AuthContext, office_id: UUID | None, today: date, horizon: date, clients: dict[UUID, str]
) -> list[DeadlineRow] | None:
    """T-08-T20 (DEC-5917): with `practice.filing_deadlines` on, the pane reads the same rows as
    HOME-03 (the viewer as owner or signer, walls applied there), open ones overdue or due by the
    horizon and the first one past it; None while the flag is off (the interim source)."""
    from abacus.kernel._flags import PRACTICE_FILING_DEADLINES
    from abacus.kernel.flags import flag_enabled
    from abacus.modules.identity.api import Forbidden
    from abacus.modules.practice.deadlines_service import rows as deadline_rows

    if not await flag_enabled(ctx.tenant, PRACTICE_FILING_DEADLINES):
        return None
    try:
        found = await deadline_rows(
            ctx, today - timedelta(days=400), horizon + timedelta(days=400), office=office_id,
            person=ctx.user_id,
        )  # fmt: skip
    except Forbidden:
        return None
    return [
        DeadlineRow(
            r.work_item_id or r.deadline_id, r.due_on,
            clients.get(r.client_id, "") if r.client_id else "", r.filing_label, r.stage_code,
            risk_of(r.due_on, today), _KIND_OF_SOURCE.get(r.source_kind, r.source_kind),
            r.deadline_id,
        )
        for r in sorted(found, key=lambda r: (r.due_on, r.filing_label, str(r.deadline_id)))
        if not r.done
    ]  # fmt: skip


async def home_view(ctx: AuthContext, office_id: UUID | None) -> HomeView:
    today = await clock.today(ctx.tenant)
    names = await names_of([ctx.user_id])
    first = (names.get(ctx.user_id) or "").split(" ", 1)[0]
    admin = metadata_only(ctx)
    tiles: list[Tile] = []
    for spec in ADMIN_TILES if admin else PRACTICE_TILES:
        found = await home_count(ctx, spec.key, office_id)
        if found is not None:
            tiles.append(Tile(spec, found))
    running = await home_count(ctx, "agent_runs_running", office_id)
    if admin:
        return HomeView(
            first, today, tiles, None, [], [], None, running.total if running else None
        )
    work = await assigned_work(ctx, office_id=office_id)
    clients = {n.client_id: n.name for n in await firm_names(ctx.tenant) if n.id == n.client_id}
    rows = [WorkRow(w, clients.get(w.client_id, "")) for w in work]
    horizon = today + timedelta(days=WINDOW)
    dated = await _filing_deadlines(ctx, office_id, today, horizon, clients)
    if dated is None:  # the interim source until `practice.filing_deadlines` is on
        dated = sorted(
            (
                DeadlineRow(
                    w.work.work_item_id, w.work.due_on, w.client, w.work.name, w.work.status,
                    risk_of(w.work.due_on, today), w.work.kind,
                )
                for w in rows
                if w.work.due_on is not None
            ),
            key=lambda d: (d.due_on, str(d.work_item_id)),
        )  # fmt: skip
    within = [d for d in dated if d.due_on <= horizon]
    beyond = next((d for d in dated if d.due_on > horizon), None)
    return HomeView(
        first,
        today,
        tiles,
        work_label(work),
        rows,
        within,
        beyond,
        running.total if running else None,
    )


__all__ = ["ADMIN_TILES", "PRACTICE_TILES", "HomeView", "home_view", "risk_of", "work_label"]
