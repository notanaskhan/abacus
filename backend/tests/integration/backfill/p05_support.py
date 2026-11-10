"""The P-05 acceptance world (ac-test-author: P-05-T07, T08; written from SPEC-650 and the 501
stubs, not from the services): one Brightwater-Hale-shaped firm with `collaboration.v2`
on, Northwind's engagement team of five, a firm member not on the engagement, a walled member and a client
contact.

Names follow the SPEC's people so that a failure reads like the story: Margaret Okonkwo (EP),
Hannah Leclerc (manager), Marcus Delaney (staff), Alicia Chen (senior), Tom Whitaker (staff),
Simone Baptiste (on the firm, not the engagement), Grace Holloway (firm admin), Victor Hale (walled
from Northwind's client).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

import httpx

from abacus.kernel.flags import forget_flags

from .support import Net, Person, Role, Site

FLAG = "collaboration.v2"


@dataclass(frozen=True)
class Collab:
    net: Net
    tenant_id: uuid.UUID
    site: Site
    other: Site  # a second engagement of the same firm (AC-27)
    margaret: Person
    hannah: Person
    marcus: Person
    alicia: Person
    tom: Person
    simone: Person
    grace: Person
    victor: Person
    client: Person

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: dict[str, object] | None = None,
        **kw: bool,
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, **kw)

    async def flag(self, on: bool) -> None:
        await self.net.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, $3, 'test-seed', 'P-05-T07') "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
            self.tenant_id,
            FLAG,
            "true" if on else "false",
        )
        forget_flags()

    async def todo(
        self,
        who: Person | None = None,
        *,
        assignee: Person | None = None,
        title: str = "Tie the cutoff item to AJE-1",
        due_on: str | None = None,
        engagement: Site | None = None,
        checklist: list[str] | None = None,
    ) -> dict[str, object]:
        """A to-do on the engagement (the one anchor kind P-05 registers before T09)."""
        body: dict[str, object] = {
            "scope_kind": "engagement",
            "engagement_id": str((engagement or self.site).engagement_id),
            "title": title,
            "assignee_user_id": str((assignee or self.marcus).user_id),
        }
        if due_on is not None:
            body["due_on"] = due_on
        if checklist is not None:
            body["checklist"] = checklist
        response = await self.call("POST", "/v1/todos", who or self.margaret, body)
        assert response.status_code == 201, response.text
        return cast(dict[str, object], response.json())

    async def thread_on(
        self,
        anchor_id: object,
        who: Person | None = None,
        body: str = "First note.",
        **extra: object,
    ) -> httpx.Response:
        payload: dict[str, object] = {
            "anchor": {"anchor_kind": "todo", "anchor_id": str(anchor_id)},
            "body": body,
            **extra,
        }
        return await self.call("POST", "/v1/comment-threads", who or self.margaret, payload)

    async def audit_actions(self, target_id: object) -> list[tuple[str, str | None]]:
        rows = await self.net.seed.rows(
            "SELECT action, actor_id FROM audit_events WHERE tenant_id = $1 "
            "AND target_id = $2 ORDER BY seq",
            self.tenant_id,
            str(target_id),
        )
        return [(r["action"], r["actor_id"]) for r in rows]


async def _named(net: Net, who: Person, name: str) -> Person:
    await net.seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    return who


async def collab(net: Net) -> Collab:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    grace = await _named(net, await seed.person(tenant_id, "firm_admin"), "Grace Holloway")
    site = await seed.site(tenant_id, grace.user_id, "Northwind")
    other = await seed.site(tenant_id, grace.user_id, "Granite")
    team: list[tuple[str, Role]] = [
        ("Margaret Okonkwo", "engagement_partner"),
        ("Hannah Leclerc", "manager"),
        ("Marcus Delaney", "staff"),
        ("Alicia Chen", "senior"),
        ("Tom Whitaker", "staff"),
    ]
    people: list[Person] = []
    for name, role in team:
        who = await _named(net, await seed.person(tenant_id), name)
        await seed.member(site, who, role)
        await seed.member(other, who, role)
        people.append(who)
    # Membership levels: the EP is a partner, Hannah a manager (firm-scope to-dos, AC-28).
    for who, level in ((people[0], "partner"), (people[1], "manager")):
        await seed.run(
            "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
            tenant_id,
            who.user_id,
            level,
        )
    simone = await _named(net, await seed.person(tenant_id), "Simone Baptiste")
    victor = await _named(net, await seed.person(tenant_id), "Victor Hale")
    await net.wall(grace, victor, site)
    client = await seed.client_contact(site)
    world = Collab(net, tenant_id, site, other, *people, simone, grace, victor, client)
    await world.flag(True)
    return world
