"""Shared stand-ins for the Q-03-T031 and T032 back-fills (TASK-1282, TASK-1283): the engagement
agent driven as its workflow drives it, without a Temporal server.

`Starts` replaces the Temporal client and records every workflow start and signal-with-start.
`World.relay` hands an event to the relay's subscriber for its type (`agents.api.SUBSCRIPTIONS`,
what the worker composes), and `World.run_agent` replays each recorded agent signal into the
agent's one activity, `handle`, as the long-lived workflow does per signal (TASK-050 design 1:
one signal, one policy activity, no business state in the workflow).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import asyncpg

from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import SUBSCRIPTIONS, AgentEvent, HandleInput
from abacus.modules.agents.engagement_agent import handle

from .support import Net, Person, Role, Seeder, Site

Json = dict[str, object]
REPO_MATRIX = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "permission-matrix"
TEAM: tuple[Role, ...] = ("engagement_partner", "manager", "senior", "staff", "reviewer")


@dataclass
class Start:
    workflow: str
    arg: object
    id: str
    signal: str | None
    payload: object


@dataclass
class Starts:
    """Stands in for the Temporal client: records starts (and signal-with-starts)."""

    calls: list[Start] = field(default_factory=list[Start])

    async def start_workflow(self, *args: object, **kwargs: object) -> None:
        run = args[0]
        name = cast(str, getattr(run, "__qualname__", repr(run)))
        self.calls.append(
            Start(
                name,
                args[1] if len(args) > 1 else None,
                cast(str, kwargs["id"]),
                cast("str | None", kwargs.get("start_signal")),
                (cast(list[object], kwargs.get("start_signal_args")) or [None])[0],
            )
        )

    def to(self, prefix: str) -> list[Start]:
        """Starts of workflows whose id begins with `prefix`, signals excluded."""
        return [c for c in self.calls if c.id.startswith(prefix) and c.signal is None]

    def signals(self) -> list[Start]:
        return [c for c in self.calls if c.signal is not None]


@dataclass
class World:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    site: Site
    team: dict[str, Person]
    starts: Starts
    handled: int = 0

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def level(self, level: int) -> None:
        """The firm's autonomy level, set by its administrator (SPEC-024 AC-5)."""
        response = await self.net.call(
            "PUT", "/v1/firm/autonomy", self.admin, body={"level": level}
        )
        assert response.status_code == 200, response.text
        assert response.json()["level"] == level

    async def flag(self, name: str, on: bool = True) -> None:
        await self.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, $3, 'test-seed', 'Q-03-T031') "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
            self.tenant_id,
            name,
            "true" if on else "false",
        )
        forget_flags()

    async def relay(
        self, event_type: str, payload: Json, event_id: uuid.UUID | None = None
    ) -> uuid.UUID:
        """The relay delivering one event to its subscriber (at least once: callers may repeat)."""
        given = event_id or uuid.uuid4()
        await SUBSCRIPTIONS[event_type](OutboxEvent(given, self.tenant_id, event_type, payload))
        return given

    async def relay_outbox(self, event_type: str) -> int:
        """Deliver every outbox row of this firm with this type, as the relay would."""
        rows = await self.seed.rows(
            "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY seq",
            self.tenant_id,
            event_type,
        )
        for row in rows:
            raw = row["payload"]
            payload = cast(Json, json.loads(raw) if isinstance(raw, str) else raw)
            await self.relay(event_type, payload, row["id"])
        return len(rows)

    async def run_agent(self) -> list[bool]:
        """Each agent signal not yet handled, through `handle`; the `end` answers, in order."""
        ended: list[bool] = []
        pending = self.starts.signals()[self.handled :]
        self.handled += len(pending)
        for call in pending:
            event = cast(AgentEvent, call.payload)
            tenant, engagement = call.id.split(":")[1:3]
            result = await handle(
                HandleInput(tenant, engagement, event.event_type, event.event_id, event.payload)
            )
            ended.append(result.end)
        return ended

    async def feed(self, who: Person | None = None) -> list[Json]:
        response = await self.net.call("GET", f"{self.base}/activity", who or self.team["manager"])
        assert response.status_code == 200, response.text
        return cast(list[Json], response.json())

    async def audit(self, action: str) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT actor_kind, actor_id, target_id FROM audit_events "
            "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )


async def make_world(net: Net, seed: Seeder, starts: Starts, label: str) -> World:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, label)
    team: dict[str, Person] = {}
    for role in TEAM:
        team[role] = await seed.person(tenant_id)
        await seed.member(site, team[role], role)
    return World(net, tenant_id, admin, site, team, starts)
