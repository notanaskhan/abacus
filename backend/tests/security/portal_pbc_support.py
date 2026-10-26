"""Seeding and portal-session helpers for the R-01-T20 suites (TASK-1351): a firm on its own portal
host, a published binder of client-visible requests, client people with engagement-scope grants,
and portal sessions minted through the pre-session routes (POR-01), as a client signs in.

Written from C5 section `portal-pbc` and DEC-333/DEC-387: a binder is client-readable when
published, marked done, or closed after it was published; its requests are the client-visible
ones, never a draft, a deleted request or one with an open delegation.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, cast

import httpx

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code, totp_at
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Net, Person, Seeder, Site

Json = dict[str, object]
FLAGS: Final = (
    "portal.sign_in_v2",
    "portal.home_v2",
    "portal.documents_v2",
    "portal.third_party_room",
    "binders.engine",
)
CLIENT_WORDS: Final = frozenset({"to_do", "done", "ignored", "returned"})
ACTIONS: Final = frozenset(
    {"upload", "ignore", "undo_ignore", "withdraw", "mark_done", "undo_mark_done", "comment"}
)
# Firm words and fields a client answer never carries (C5 portal-pbc §1, INV-4).
FIRM_WORDS: Final = (
    "needs review",
    "needs_review",
    "Received ✓",
    "not_applicable",
    "firm_owner",
    "owed_by",
    "latest_upload",
    "match_confidence",
    "confidence",
    "amount",
    "screening",
    "verdict",
    "Accrued",
)


@dataclass
class Binder:
    """One firm with a published 2025 binder on one engagement: requests by title."""

    net: Net
    seed: Seeder
    tenant: uuid.UUID
    host: str
    firm_name: str
    admin: Person
    partner: Person
    site: Site
    binder: uuid.UUID
    categories: dict[str, uuid.UUID]
    items: dict[str, uuid.UUID] = field(default_factory=dict[str, uuid.UUID])

    @property
    def eid(self) -> uuid.UUID:
        return self.site.engagement_id

    async def request(
        self,
        title: str,
        category: str,
        *,
        status: str = "requested",
        visible: bool = True,
        assignee: Person | None = None,
        binder: uuid.UUID | None = None,
    ) -> uuid.UUID:
        item = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, title, category_id, client_visible, "
                "due_on, client_assignee_user_id) VALUES ($1, $2, $3, $4, 'Documents', $5, $4, "
                "$6, $7, current_date + 30, $8) RETURNING id",
                self.tenant,
                self.eid,
                binder or self.binder,
                title,
                self.admin.user_id,
                self.categories.get(category),
                visible,
                assignee.user_id if assignee else None,
            ),
        )
        if visible:
            await self.seed.run(
                "UPDATE request_items SET status = $2, requested_at = now(), "
                "firm_owner_user_id = $3 WHERE id = $1",
                item,
                status,
                self.partner.user_id,
            )
        self.items[title] = item
        return item

    async def client(self, name: str, role: str = "owner") -> tuple[Person, str]:
        """A client person with an engagement-scope grant (`owner` is the client admin)."""
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        await self.seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
        await self.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
            "granted_by) VALUES ($1, $2, $3, 'engagement', $4, $5)",
            self.tenant,
            who.user_id,
            role,
            self.eid,
            self.admin.user_id,
        )
        email = cast(
            str, await self.seed.value("SELECT email FROM users WHERE id = $1", who.user_id)
        )
        return who, email

    async def outsider(self, name: str, org: str) -> tuple[Person, uuid.UUID, str]:
        """A client-side person with no role here, and their contact on the client (a third
        party once a request is delegated to them)."""
        who = await self.seed.person(self.tenant)
        await self.seed.run(
            "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            who.user_id,
        )
        await self.seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
        email = cast(
            str, await self.seed.value("SELECT email FROM users WHERE id = $1", who.user_id)
        )
        contact = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO contacts (tenant_id, client_id, display_name, email, "
                "organisation_name, contact_kind, user_id) VALUES ($1, $2, $3, $4, $5, "
                "'third_party', $6) RETURNING id",
                self.tenant,
                self.site.client_id,
                name,
                email,
                org,
                who.user_id,
            ),
        )
        return who, contact, email

    async def delegate(self, item: uuid.UUID, contact: uuid.UUID) -> httpx.Response:
        return await self.net.call(
            "POST",
            f"/v1/engagements/{self.eid}/request-items/{item}/delegate",
            self.partner,
            body={"contact_id": str(contact)},
        )

    async def firm(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> httpx.Response:
        return await self.net.call(method, path, self.partner, body=body)


async def portal_firm(net: Net, label: str) -> tuple[uuid.UUID, str, Person]:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1351')",
            tenant,
            flag,
        )
    host = f"{label}-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return tenant, host, await seed.person(tenant, "firm_admin")


async def new_binder(
    net: Net,
    label: str,
    *,
    kind: str = "organizer",
    status: str = "published",
    categories: tuple[str, ...] = ("Income", "Health & Medical"),
    firm: tuple[uuid.UUID, str, Person] | None = None,
) -> Binder:
    seed = net.seed
    tenant, host, admin = firm or await portal_firm(net, label)
    firm_name = cast(str, await seed.value("SELECT name FROM firms WHERE tenant_id = $1", tenant))
    site = await seed.site(tenant, admin.user_id, label)
    partner = await seed.person(tenant)
    await seed.member(site, partner, "engagement_partner")
    binder = await _list(seed, tenant, site.engagement_id, partner, kind=kind, status=status)
    cats: dict[str, uuid.UUID] = {}
    for pos, name in enumerate(categories):
        cats[name] = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO request_categories (tenant_id, request_list_id, name, position) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                tenant,
                binder,
                name,
                pos,
            ),
        )
    return Binder(net, seed, tenant, host, firm_name, admin, partner, site, binder, cats)


async def _list(
    seed: Seeder,
    tenant: uuid.UUID,
    engagement: uuid.UUID,
    by: Person,
    *,
    kind: str,
    status: str,
    part: int = 1,
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, name, kind, part, status, "
            "published_at, published_by) VALUES ($1, $2, '2025 Binder', $3, $4, $5, "
            "CASE WHEN $5 = 'draft' THEN NULL ELSE now() END, "
            "CASE WHEN $5 = 'draft' THEN NULL ELSE $6::uuid END) RETURNING id",
            tenant,
            engagement,
            kind,
            part,
            status,
            by.user_id,
        ),
    )


async def another_list(b: Binder, *, status: str, part: int) -> uuid.UUID:
    return await _list(
        b.seed, b.tenant, b.eid, b.partner, kind="organizer", status=status, part=part
    )


async def _verify(http: httpx.AsyncClient, host: str, email: str) -> Json:
    start = await http.post("/v1/portal/auth/start", json={"email": email}, headers={"host": host})
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers={"host": host},
    )
    http.cookies.clear()
    assert verified.status_code == 200, verified.text
    return cast(Json, verified.json())


async def session(http: httpx.AsyncClient, host: str, email: str) -> str:
    """A signed-in portal session's access token, the second step set up when asked."""
    body = await _verify(http, host, email)
    if body["state"] == "signed_in":
        return cast(str, body["access_token"])
    assert body["state"] == "mfa_setup_required", body
    token = cast(str, body["mfa_token"])
    setup = await http.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers={"host": host}
    )
    assert setup.status_code == 200, setup.text
    done = await http.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": totp_at(setup.json()["manual_key"], time.time())},
        headers={"host": host},
    )
    http.cookies.clear()
    assert done.status_code == 200, done.text
    signed = done.json()["session"]
    assert signed["state"] == "signed_in", signed
    return cast(str, signed["access_token"])


@dataclass(frozen=True)
class Portal:
    """One signed-in client person's calls on the firm's portal host."""

    http: httpx.AsyncClient
    host: str
    token: str

    async def get(self, path: str) -> httpx.Response:
        self.http.cookies.clear()
        return await self.http.get(
            path, headers={"host": self.host, "authorization": f"Bearer {self.token}"}
        )

    async def post(
        self, path: str, body: Mapping[str, object] | None = None, *, key: str | None = None
    ) -> httpx.Response:
        self.http.cookies.clear()
        headers = {"host": self.host, "authorization": f"Bearer {self.token}"}
        if key is not None:
            headers["Idempotency-Key"] = key
        return await self.http.post(path, json=body, headers=headers)


async def signed_in(b: Binder, email: str) -> Portal:
    return Portal(b.net.http, b.host, await session(b.net.http, b.host, email))


def rows_of(binder: Json) -> list[Json]:
    """Every row of a POR-03 answer, groups or bands."""
    out: list[Json] = []
    for key in ("groups", "bands"):
        for block in cast(list[Json], binder.get(key) or []):
            out.extend(cast(list[Json], block["rows"]))
    return out
