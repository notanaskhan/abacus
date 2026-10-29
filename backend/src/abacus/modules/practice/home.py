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
    work: AssignedWork
    due_on: date
    client: str
    risk: DueRisk


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
    dated = sorted(
        (
            DeadlineRow(w.work, w.work.due_on, w.client, risk_of(w.work.due_on, today))
            for w in rows
            if w.work.due_on is not None
        ),
        key=lambda d: (d.due_on, str(d.work.work_item_id)),
    )
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
