"""ADR-014, AGENTS.md non-negotiable 1: a request for another firm's record returns 404 or 403
and no data, whoever asks and however it asks.

Firm A's people (every firm role and an engagement partner) ask for firm B's engagement,
request item, evidence version, wall, staff invitation and notification by id; list and search
what A can see; try to write into B; and ask with a tenant header naming B. Then the database
itself: under A's tenant, no tenant-scoped table returns a row of B's. Each control proves the
same call works for B's own people, so a wrong path cannot pass as "not found".
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import cast

import httpx
import pytest
from sqlalchemy import column, func, select, table, text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session

from .support import FIRM_ROLES, Json, Net, Person, Seeder, Site

ASKERS = (*FIRM_ROLES, "engagement_partner")
NOT_FOUND = {"detail": "not found"}
FORBIDDEN = {"detail": "forbidden"}


@dataclass(frozen=True)
class Two:
    """Firm A (people who ask) and firm B (the records they must not reach)."""

    net: Net
    a: uuid.UUID
    b: uuid.UUID
    site_a: Site
    site_b: Site
    admin_a: Person
    admin_b: Person
    wall_id: uuid.UUID
    invitation_id: uuid.UUID
    notification_id: uuid.UUID

    async def asker(self, role: str) -> Person:
        firm_role = role if role in FIRM_ROLES else None
        who = await self.net.seed.person(self.a, firm_role)
        await self.net.seed.member(
            self.site_a, who, "manager" if firm_role else "engagement_partner"
        )
        return who

    def leaks(self, response: httpx.Response) -> list[str]:
        tokens = {
            "engagement": str(self.site_b.engagement_id),
            "client": str(self.site_b.client_id),
            "item": str(self.site_b.item_id),
            "version": str(self.site_b.version_id),
            "name": self.site_b.marker,
            "firm": str(self.b),
            "wall": str(self.wall_id),
            "invitation": str(self.invitation_id),
            "notification": str(self.notification_id),
        }
        return [kind for kind, token in tokens.items() if token in response.text]


@pytest.fixture
async def two(net: Net, seed: Seeder) -> Two:
    a, b = await seed.firm(), await seed.firm()
    admin_a = await seed.person(a, "firm_admin")
    admin_b = await seed.person(b, "firm_admin")
    site_a = await seed.site(a, admin_a.user_id, "mine")
    site_b = await seed.site(b, admin_b.user_id, "theirs")
    await seed.member(site_b, admin_b, "engagement_partner")
    # B has a wall, a pending staff invitation and a notification for one of its people.
    walled = await seed.person(b)
    await net.wall(admin_b, walled, site_b)
    wall_id = cast(
        uuid.UUID, await seed.value("SELECT id FROM ethical_walls WHERE tenant_id = $1", b)
    )
    # G-01-T05 (DEC-285): a real firm invites only once provisioning has set its seats.
    await seed.run(
        "INSERT INTO firm_settings (tenant_id, section, key, value, updated_by) "
        "VALUES ($1, 'plan', 'seats', '100'::jsonb, $2)",
        b,
        admin_b.user_id,
    )
    invited = await net.call(
        "POST",
        "/v1/firm/staff/invitations",
        admin_b,
        body={"email": "new.partner@theirs.example", "firm_role": "firm_admin"},
    )
    assert invited.status_code in (200, 201, 202), invited.text
    invitation_id = cast(
        uuid.UUID, await seed.value("SELECT id FROM staff_invitations WHERE tenant_id = $1", b)
    )
    notification_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO notifications (id, tenant_id, recipient_user_id, kind, event_id, "
        "engagement_id, subject_type, subject_id) "
        "VALUES ($1, $2, $3, 'evidence.uploaded', $4, $5, 'evidence_version', $6)",
        notification_id,
        b,
        admin_b.user_id,
        uuid.uuid4(),
        site_b.engagement_id,
        site_b.version_id,
    )
    return Two(
        net, a, b, site_a, site_b, admin_a, admin_b, wall_id, invitation_id, notification_id
    )


COUNTS = {
    "request_items": "SELECT count(*) FROM request_items WHERE tenant_id = $1",
    "engagement_members": "SELECT count(*) FROM engagement_members WHERE tenant_id = $1",
    "ethical_walls": "SELECT count(*) FROM ethical_walls WHERE tenant_id = $1",
    "audit_events": "SELECT count(*) FROM audit_events WHERE tenant_id = $1",
}


async def _counts(seed: Seeder, tenant_id: uuid.UUID) -> dict[str, object]:
    return {name: await seed.value(sql, tenant_id) for name, sql in COUNTS.items()}


def _gone(two: Two, response: httpx.Response) -> None:
    """Refused as not found or forbidden, with nothing of firm B in it."""
    assert response.status_code in (403, 404), response.text
    assert response.json() in (NOT_FOUND, FORBIDDEN)
    assert two.leaks(response) == []


# --- reading another firm's record by id ---------------------------------------------------------

READS = [
    "/v1/engagements/{e}",
    "/v1/engagements/{e}/team",
    "/v1/engagements/{e}/setup",
    "/v1/engagements/{e}/request-items",
    "/v1/engagements/{e}/request-items/{i}/versions",
    "/v1/engagements/{e}/request-items/{i}/comments",
    "/v1/engagements/{e}/evidence-versions",
    "/v1/engagements/{e}/evidence-versions/{v}/content",
    "/v1/engagements/{e}/screening-results",
    "/v1/engagements/{e}/review-queue",
    "/v1/engagements/{e}/board-summary",
    "/v1/engagements/{e}/connection",
    "/v1/engagements/{e}/activity",
    "/v1/engagements/{e}/graph",
    "/v1/engagements/{e}/findings",
    "/v1/engagements/{e}/procedures",
]


def _path(template: str, site: Site) -> str:
    return template.format(e=site.engagement_id, i=site.item_id, v=site.version_id)


@pytest.mark.parametrize("role", ASKERS)
@pytest.mark.parametrize("template", READS)
async def test_adr014_another_firms_record_is_not_found_by_id(
    two: Two, role: str, template: str
) -> None:
    asker = await two.asker(role)
    _gone(two, await two.net.call("GET", _path(template, two.site_b), asker))
    # The same path works for the firm's own people on the firm's own record.
    mine = await two.net.call("GET", _path(template, two.site_a), asker)
    assert mine.status_code != 404 or template.endswith("/content"), mine.text


@pytest.mark.parametrize("template", READS[:5])
async def test_adr014_the_control_firm_b_reads_its_own_records(two: Two, template: str) -> None:
    response = await two.net.call("GET", _path(template, two.site_b), two.admin_b)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("role", ASKERS)
async def test_adr014_another_firms_wall_invitation_and_notification_are_not_found(
    two: Two, role: str
) -> None:
    asker = await two.asker(role)
    for method, path in (
        ("POST", f"/v1/walls/{two.wall_id}/remove"),
        ("POST", f"/v1/firm/staff/invitations/{two.invitation_id}/resend"),
        ("POST", f"/v1/firm/staff/invitations/{two.invitation_id}/revoke"),
        ("POST", f"/v1/notifications/{two.notification_id}/read"),
        ("PUT", f"/v1/firm/staff/{two.admin_b.user_id}/role"),
        ("POST", f"/v1/firm/staff/{two.admin_b.user_id}/revoke"),
    ):
        response = await two.net.call(method, path, asker, body={"firm_role": None})
        _gone(two, response)
    # Nothing changed in B.
    assert (
        await two.net.seed.value("SELECT status FROM ethical_walls WHERE id = $1", two.wall_id)
        == "active"
    )
    assert (
        await two.net.seed.value(
            "SELECT status FROM staff_invitations WHERE id = $1", two.invitation_id
        )
        == "pending"
    )
    assert (
        await two.net.seed.value(
            "SELECT status FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            two.b,
            two.admin_b.user_id,
        )
        == "active"
    )
    assert (
        await two.net.seed.value(
            "SELECT read_at FROM notifications WHERE id = $1", two.notification_id
        )
        is None
    )


# --- lists and searches --------------------------------------------------------------------------

LISTS = [
    "/v1/engagements",
    "/v1/firm/search/request-items?q=Bank%20confirmation",
    "/v1/firm/search/findings?q=Cut-off",
    "/v1/firm/clients/search?q=Client",
    "/v1/firm/clients",
    "/v1/firm/members",
    "/v1/firm/staff",
    "/v1/walls",
    "/v1/notifications",
    "/v1/firm/confirmations",
    "/v1/firm/waiting/overdue",
    "/v1/firm/waiting/review",
    "/v1/firm/waiting/fieldwork",
    "/v1/knowledge/documents",
    "/v1/methodology/templates",
    "/v1/support-sessions",
    "/v1/firm/audit-events",
]


@pytest.mark.parametrize("role", ASKERS)
@pytest.mark.parametrize("path", LISTS)
async def test_adr014_a_list_or_search_never_shows_another_firms_rows(
    two: Two, role: str, path: str
) -> None:
    await two.net.seed.run(
        "INSERT INTO findings (tenant_id, engagement_id, title, raised_by) "
        "VALUES ($1, $2, $3, $4)",
        two.b,
        two.site_b.engagement_id,
        f"Cut-off error {two.site_b.marker}",
        two.admin_b.user_id,
    )
    asker = await two.asker(role)
    response = await two.net.call("GET", path, asker)
    assert response.status_code in (200, 403), (path, response.text)
    assert two.leaks(response) == [], path
    if response.status_code == 200 and path == "/v1/engagements":  # the control: her own firm
        assert str(two.site_a.engagement_id) in response.text


# --- writing into another firm -------------------------------------------------------------------


@pytest.mark.parametrize("role", ASKERS)
async def test_adr014_nothing_can_be_written_into_another_firm(two: Two, role: str) -> None:
    asker = await two.asker(role)
    seed = two.net.seed
    before = await _counts(seed, two.b)
    requests: tuple[tuple[str, str, Json], ...] = (
        (
            "POST",
            f"/v1/engagements/{two.site_b.engagement_id}/request-items",
            {"description": "Planted", "audit_area": "Cash"},
        ),
        (
            "POST",
            f"/v1/engagements/{two.site_b.engagement_id}/team",
            {"user_id": str(asker.user_id), "role": "engagement_partner"},
        ),
        (
            "POST",
            f"/v1/engagements/{two.site_b.engagement_id}/self-join",
            {"role": "engagement_partner"},
        ),
        (
            "POST",
            "/v1/walls",
            {"user_id": str(asker.user_id), "client_id": str(two.site_b.client_id)},
        ),
        ("PUT", f"/v1/engagements/{two.site_b.engagement_id}/materiality", {"amount": "1"}),
    )
    for method, path, body in requests:
        response = await two.net.call(method, path, asker, body=body)
        assert response.status_code in (403, 404, 422), (path, response.text)
        assert two.leaks(response) == [], path
    assert await _counts(seed, two.b) == before
    assert (
        await seed.value(
            "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            two.site_b.engagement_id,
            asker.user_id,
        )
        == 0
    )


async def test_adr014_an_engagement_cannot_be_created_for_another_firms_client(two: Two) -> None:
    response = await two.net.call(
        "POST",
        "/v1/engagements",
        two.admin_a,
        body={
            "client_entity_id": str(two.site_b.entity_id),
            "name": "Planted engagement",
            "fiscal_period_start": "2025-01-01",
            "fiscal_period_end": "2025-12-31",
        },
    )
    assert response.status_code in (404, 422), response.text
    assert two.leaks(response) == []
    assert (
        await two.net.seed.value(
            "SELECT count(*) FROM engagements WHERE name = 'Planted engagement'"
        )
        == 0
    )


# --- the tenant header ---------------------------------------------------------------------------


async def test_adr014_a_header_naming_another_firm_gives_nothing_to_a_non_member(
    two: Two,
) -> None:
    asker = await two.asker("firm_admin")
    for path in ("/v1/engagements", f"/v1/engagements/{two.site_b.engagement_id}"):
        response = await two.net.call("GET", path, asker, tenant=two.b)
        assert response.status_code == 403, response.text
        assert response.json() == FORBIDDEN
        assert two.leaks(response) == []


async def test_adr014_a_member_of_both_firms_sees_only_the_firm_the_header_names(
    two: Two, seed: Seeder
) -> None:
    both = await seed.person(two.a, "firm_admin", also=two.b)
    in_a = await two.net.call(
        "GET", f"/v1/engagements/{two.site_b.engagement_id}", both, tenant=two.a
    )
    _gone(two, in_a)  # firm B's id asked of firm A's tenant
    in_b = await two.net.call(
        "GET", f"/v1/engagements/{two.site_b.engagement_id}", both, tenant=two.b
    )
    assert in_b.status_code == 200, in_b.text  # the control: the same id under B's own tenant
    listing = await two.net.call("GET", "/v1/engagements", both, tenant=two.a)
    assert listing.status_code == 200
    assert str(two.site_b.engagement_id) not in listing.text
    assert str(two.site_a.engagement_id) in listing.text


# --- the database itself -------------------------------------------------------------------------


async def test_adr014_under_a_tenant_no_table_returns_another_tenants_rows(
    two: Two, seed: Seeder
) -> None:
    """Row-level security, table by table, for every table that has a `tenant_id`."""
    tables = [
        str(r["table_name"])
        for r in await seed.rows(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'tenant_id' ORDER BY table_name"
        )
    ]
    assert len(tables) > 20
    seen = 0
    leaked: dict[str, int] = {}
    for name in tables:
        owned = table(name, column("tenant_id"))
        query = select(func.count()).select_from(owned).where(column("tenant_id") == two.b)
        try:
            async with tenant_session(
                TenantContext(two.a, "human", str(two.admin_a.user_id))
            ) as s:
                found = (await s.execute(query)).scalar_one()
        except DBAPIError:  # the app role has no right to read it at all: nothing leaks
            continue
        seen += 1
        if found:
            leaked[name] = int(found)
    assert seen > 20
    assert leaked == {}


async def test_adr014_under_a_tenant_a_row_cannot_be_written_for_another(
    two: Two,
) -> None:
    with pytest.raises(DBAPIError):
        async with tenant_session(TenantContext(two.a, "human", str(two.admin_a.user_id))) as s:
            await s.execute(
                text("INSERT INTO clients (tenant_id, name) VALUES (:b, 'Planted')"),
                {"b": two.b},
            )
    assert await two.net.seed.value("SELECT count(*) FROM clients WHERE name = 'Planted'") == 0
