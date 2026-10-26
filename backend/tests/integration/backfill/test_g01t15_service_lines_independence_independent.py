# ac-test-author: ayushkbhatia
"""G-01 AC4.5, AC6.1 to AC6.3, AC10.1 to AC10.3; SPEC-002 AC-21 to AC-24; SPEC-024 AC-9 to AC-12
(G-01-T12, G-01-T13; G-01-T15): service-line need-to-know, the seasonal access-end job and the
annual independence confirmation, read from G-01 §3.4, §3.6, §3.10, §4.3 and §4.4, SPEC-002
Story 6, SPEC-024 AC-9 to AC-12, the contract `docs/contracts/firm-settings.md`, the identity
permission matrix, and DEC-380 and DEC-381. Expectations come from the specification, never from
the implementation.

HTTP through `create_app()` against the migrated Postgres, with `firm_settings.v2` on. The
access-end job is driven through its public activity (`identity.api.SCHEDULES` names it; the
activity is `identity.api.sweep_access_ends_activity`) under `kernel.clock.frozen`, so "the
firm's day" is whatever instant the test sets. P-07's reader is
`identity.api.has_current_annual_confirmation`.
Decisions followed instead of the epic's wording:
- DEC-380: a line set to "Service line" lets its members read the line's non-attest engagements
  as the `staff` role reads them, plain reads only; never Audit, an attest client, a walled
  client, an offshore member, a firm or security admin or level `admin`. No row reads every line
  "Engagement team only", "Hand-offs only", version 0.
- DEC-381: the job is hourly (not 00:15) and ends a member when `access_ends_on` is before the
  firm's business date in the firm's own time zone; on behalf of whoever last set the date; one
  T-7 notice per firm and date; the statement is its own versioned resource
  (`PUT /v1/firm/independence/statement`); a confirmation is for the current business year only
  and names the statement version read.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import (
    RULES,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    has_current_annual_confirmation,
    sweep_access_ends_activity,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)

from .support import Migrated, Net, Person, Seeder

CHECK_VIOLATION: Final = "23514"

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FLAG: Final = "firm_settings.v2"
LINES: Final = "/v1/firm/service-lines"
STATEMENT: Final = "/v1/firm/independence/statement"
MINE: Final = "/v1/me/independence/annual"
ANNUAL: Final = "/v1/firm/independence/annual"
STAFF: Final = "/v1/firm/staff"
CHICAGO: Final = ZoneInfo("America/Chicago")
OCT_31: Final = date(2026, 10, 31)
MID_YEAR: Final = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
WORK_ITEM_KINDS: Final = {
    "tax_compliance": "tax_return",
    "cas_monthly_close": "close",
    "advisory": "advisory_project",
}
NEW_WRITES: Final = (
    "service_line_policy.manage",
    "independence.annual_confirm",
    "firm.manage_settings",
    "firm.manage_users",
)


# ================================================================================================
# The firm
# ================================================================================================


@dataclass(frozen=True)
class Firm:
    net: Net
    seed: Seeder
    tenant_id: uuid.UUID
    grace: Person  # Grace Holloway: firm admin

    async def person(
        self,
        firm_role: str | None = None,
        *,
        level: str = "staff",
        lines: tuple[str, ...] = (),
        offshore: bool = False,
        ends: date | None = None,
    ) -> Person:
        who = await self.seed.person(self.tenant_id, firm_role)
        await self.seed.run(
            "UPDATE memberships SET level = $3, service_lines = $4, offshore = $5, "
            "access_ends_on = $6 WHERE tenant_id = $1 AND user_id = $2",
            self.tenant_id,
            who.user_id,
            level,
            list(lines),
            offshore,
            ends if ends is not None else (date(2027, 10, 31) if level == "seasonal" else None),
        )
        return who

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None, *, mfa: bool = True
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, mfa=mfa)

    async def audit(self, action: str) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT actor_kind, actor_id, on_behalf_of_user_id, target_id::text AS target_id, "
            "coalesce(before_ref::text, '') || coalesce(after_ref::text, '') AS refs "
            "FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )

    async def outbox(self, event_type: str) -> list[str]:
        rows = await self.seed.rows(
            "SELECT payload::text AS p FROM outbox WHERE tenant_id = $1 AND event_type = $2 "
            "ORDER BY occurred_at, id",
            self.tenant_id,
            event_type,
        )
        return [str(r["p"]) for r in rows]

    async def access_changed_for(self, who: Person) -> int:
        return len([p for p in await self.outbox("access.changed") if str(who.user_id) in p])

    async def membership(self, who: Person) -> asyncpg.Record:
        return (
            await self.seed.rows(
                "SELECT status, revoked_reason, revoked_on_behalf_of, access_ends_on "
                "FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                self.tenant_id,
                who.user_id,
            )
        )[0]

    def auth(self, who: Person, firm_role: str | None = None) -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant_id, "human", str(who.user_id)),
            who.user_id,
            uuid.uuid4(),
            cast(None, firm_role),
            datetime.now(UTC) - timedelta(minutes=1),
        )

    def agent(self, actions: tuple[str, ...]) -> AgentContext:
        run = uuid.uuid4()
        return AgentContext(
            tenant=TenantContext(
                self.tenant_id, "agent", f"agent:probe:{run}", self.grace.user_id
            ),
            agent_id="probe",
            agent_run_id=run,
            engagement_id=None,
            task_scope=frozenset(actions),
            initiator=self.auth(self.grace, "firm_admin"),
            issued_by=_ISSUER,
        )

    async def engagement(
        self, client_id: uuid.UUID | None = None, *, kind: str = "tax_compliance"
    ) -> Engagement:
        """An open engagement of `kind` (its service line follows the type) with one request item
        whose description carries a marker no one else may read."""
        marker = f"{kind}-{uuid.uuid4().hex[:8]}"
        if client_id is None:
            client_id = cast(
                uuid.UUID,
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                    self.tenant_id,
                    f"Client {marker}",
                ),
            )
        entity_id = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant_id,
            client_id,
            f"Entity {marker}",
        )
        engagement_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) VALUES "
                "($1, $2, $3, $4, $5, 'active', '2025-01-01', '2025-12-31', $6) RETURNING id",
                self.tenant_id,
                client_id,
                entity_id,
                f"Engagement {marker}",
                kind,
                self.grace.user_id,
            ),
        )
        await self.seed.run(
            "INSERT INTO engagement_acceptance (tenant_id, engagement_id, kind, decision, "
            "decided_by, documented_at, independence_concluded_by, independence_concluded_at, "
            "independence_documented_at) VALUES ($1, $2, 'continuance', 'accepted', "
            "'test-seed', 'Seeded', 'test-seed', clock_timestamp(), 'Seeded')",
            self.tenant_id,
            engagement_id,
        )
        # A binder joins a work item (types without an automatic one get theirs here).
        await self.seed.run(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) SELECT $1, $2, $3, $4, $5, $6, $7 WHERE NOT EXISTS "
            "(SELECT 1 FROM work_items WHERE tenant_id = $1 AND engagement_id = $2)",
            self.tenant_id,
            engagement_id,
            client_id,
            entity_id,
            WORK_ITEM_KINDS.get(kind, "assurance"),
            f"Work {marker}",
            self.grace.user_id,
        )
        list_id = await self.seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
            self.tenant_id,
            engagement_id,
        )
        await self.seed.run(
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) VALUES ($1, $2, $3, $4, 'Cash', $5)",
            self.tenant_id,
            engagement_id,
            list_id,
            f"Bank statements {marker}",
            self.grace.user_id,
        )
        return Engagement(engagement_id, client_id, marker)


@dataclass(frozen=True)
class Engagement:
    id: uuid.UUID
    client_id: uuid.UUID
    marker: str


async def _firm(net: Net, zone: str = "America/Chicago") -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET time_zone = $2 WHERE tenant_id = $1", tenant, zone)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T15')",
        tenant,
        FLAG,
    )
    grace = await seed.person(tenant, "firm_admin")
    await seed.run(
        "UPDATE memberships SET level = 'admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        grace.user_id,
    )
    return Firm(net, seed, tenant, grace)


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net)


def _body(response: httpx.Response, *status: int) -> Json:
    assert response.status_code in (status or (200,)), response.text
    return cast(Json, response.json())


def _detail(response: httpx.Response) -> object:
    return cast(Json, response.json()).get("detail")


def _ct(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=CHICAGO)


# ================================================================================================
# Service lines: the policies (SPEC-002 AC-21; G-01 AC10.1)
# ================================================================================================


def _policy(version: object, to: str = "service_line", **extra: object) -> Json:
    return {
        "version": version,
        "enabled": True,
        "lead_user_id": None,
        "content_visible_to": to,
        "cross_line_access": "handoffs_only",
        **extra,
    }


async def _lines(firm: Firm, who: Person | None = None) -> dict[str, Json]:
    rows = cast(list[Json], (await firm.call("GET", LINES, who or firm.grace)).json())
    return {cast(str, r["service_line"]): r for r in rows}


async def _set(firm: Firm, line: str, to: str = "service_line", who: Person | None = None) -> Json:
    version = (await _lines(firm))[line]["version"]
    return _body(
        await firm.call("PUT", f"{LINES}/{line}", who or firm.grace, _policy(version, to))
    )


async def test_ac21_a_firm_without_rows_reads_four_lines_team_only_at_version_0(
    firm: Firm,
) -> None:
    response = await firm.call("GET", LINES, firm.grace)
    rows = cast(list[Json], _body(response))
    assert [r["service_line"] for r in rows] == ["audit", "tax", "cas", "advisory"]
    for row in rows:
        assert (row["enabled"], row["content_visible_to"], row["cross_line_access"]) == (
            True,
            "engagement_team_only",
            "handoffs_only",
        )
        assert row["version"] == 0
    daniel = await firm.person(level="partner")
    assert (await firm.call("GET", LINES, daniel)).status_code == 200  # partners read settings
    kevin = await firm.person(lines=("tax",))
    assert (await firm.call("GET", LINES, kevin)).status_code in (403, 404)


async def test_ac21_audit_can_never_be_widened_through_the_api_or_the_database(
    firm: Firm,
) -> None:
    refused = await firm.call("PUT", f"{LINES}/audit", firm.grace, _policy(0))
    assert refused.status_code == 422, refused.text
    assert _detail(refused) == "audit_locked"
    assert (await _lines(firm))["audit"]["content_visible_to"] == "engagement_team_only"
    assert await firm.audit("service_line_policy.updated") == []
    # As Grace herself, through the app's own session (DEC-383's actor trigger passes), so only
    # the Audit CHECK can refuse.
    with pytest.raises(IntegrityError) as raised:
        async with tenant_session(
            TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
        ) as session:
            await session.execute(
                text(
                    "INSERT INTO service_line_policies (tenant_id, service_line, enabled, "
                    "content_visible_to, cross_line_access, updated_by) "
                    "VALUES (:t, 'audit', true, 'service_line', 'handoffs_only', :by)"
                ),
                {"t": firm.tenant_id, "by": firm.grace.user_id},
            )
    assert getattr(raised.value.orig, "sqlstate", None) == CHECK_VIOLATION


async def test_ac21_a_change_is_an_admins_with_fresh_mfa_against_the_version_and_audited(
    firm: Firm,
) -> None:
    daniel = await firm.person(level="partner")
    kevin = await firm.person(lines=("tax",))
    # ADR-183 condition 4 (Ayush, 2026-10-26): security admins never manage the policy.
    felix = await firm.person("security_admin", level="admin")
    for who in (felix, kevin):
        refused = await firm.call("PUT", f"{LINES}/tax", who, _policy(0))
        assert refused.status_code in (403, 404), refused.text
    stale_mfa = await firm.call("PUT", f"{LINES}/tax", firm.grace, _policy(0), mfa=False)
    assert stale_mfa.status_code == 403, stale_mfa.text
    assert (await _lines(firm))["tax"]["version"] == 0
    saved = _body(await firm.call("PUT", f"{LINES}/tax", firm.grace, _policy(0)))
    assert (saved["content_visible_to"], saved["version"]) == ("service_line", 1)
    stale = await firm.call("PUT", f"{LINES}/tax", firm.grace, _policy(0, "engagement_team_only"))
    assert stale.status_code == 409, stale.text
    assert _detail(stale) == "stale_version"
    assert (await _lines(firm))["tax"]["content_visible_to"] == "service_line"
    # A partner changes it too (with fresh MFA; ADR-183 condition 4).
    by_daniel = await firm.call("PUT", f"{LINES}/tax", daniel, _policy(1, "engagement_team_only"))
    assert by_daniel.status_code == 200, by_daniel.text
    rows = await firm.audit("service_line_policy.updated")
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [
        ("human", str(firm.grace.user_id)),
        ("human", str(daniel.user_id)),
    ]
    assert len(await firm.outbox("service_line_policy.changed")) == 2
    # A lead must be the firm's active staff.
    outsider = await firm.person()
    await firm.seed.revoke(outsider)
    bad_lead = await firm.call(
        "PUT", f"{LINES}/tax", firm.grace, _policy(2, lead_user_id=str(outsider.user_id))
    )
    assert bad_lead.status_code == 422, bad_lead.text
    assert _detail(bad_lead) == "service_line_lead_invalid"


# ================================================================================================
# Service lines: the reach (SPEC-002 AC-22 to AC-24; G-01 AC10.2, AC10.3)
# ================================================================================================


async def _reads(firm: Firm, who: Person, engagement: Engagement) -> bool:
    """Kevin's engagement read and its content (request items), over HTTP."""
    record = await firm.call("GET", f"/v1/engagements/{engagement.id}", who)
    items = await firm.call("GET", f"/v1/engagements/{engagement.id}/request-items", who)
    if record.status_code == 200 and items.status_code == 200:
        assert engagement.marker in items.text
        return True
    assert record.status_code in (403, 404), record.text
    assert items.status_code in (403, 404), items.text
    assert engagement.marker not in items.text
    return False


async def _listed(firm: Firm, who: Person) -> set[uuid.UUID]:
    response = await firm.call("GET", "/v1/engagements", who)
    if response.status_code != 200:
        return set()
    return {uuid.UUID(str(e["id"])) for e in cast(list[Json], response.json())}


async def test_ac22_opening_tax_lets_kevin_read_and_list_and_narrowing_ends_it_next_request(
    firm: Firm,
) -> None:
    kevin = await firm.person(lines=("tax",))
    lena = await firm.person(level="seasonal", lines=("tax",))
    cara = await firm.person(lines=("cas",))
    tax = await firm.engagement()
    cas = await firm.engagement(kind="cas_monthly_close")
    assert not await _reads(firm, kevin, tax)
    assert tax.id not in await _listed(firm, kevin)
    before = {who: await firm.access_changed_for(who) for who in (kevin, lena, cara)}

    await _set(firm, "tax")
    assert await _reads(firm, kevin, tax)
    assert tax.id in await _listed(firm, kevin)
    # Tax's reach is Tax's: CAS stays closed to Kevin, and Tax stays closed to Cara.
    assert not await _reads(firm, kevin, cas)
    assert not await _reads(firm, cara, tax)
    assert await firm.access_changed_for(kevin) == before[kevin] + 1
    assert await firm.access_changed_for(lena) == before[lena] + 1
    assert await firm.access_changed_for(cara) == before[cara]

    await _set(firm, "tax", "engagement_team_only")
    assert not await _reads(firm, kevin, tax)  # the very next request
    assert tax.id not in await _listed(firm, kevin)
    assert await firm.access_changed_for(kevin) == before[kevin] + 2


async def test_ac23_the_reach_is_read_only_it_never_grants_a_write(firm: Firm) -> None:
    kevin = await firm.person(lines=("tax",))
    tax = await firm.engagement()
    await _set(firm, "tax")
    resource = await engagement_resource(TenantContext(firm.tenant_id, "human", "p"), tax.id)
    await authorise(firm.auth(kevin), "request_item.read", resource)
    # `staff` holds these on an engagement team; the line reader holds none of them.
    for write in ("request_item.mark_ready", "request_item.send", "comment.share"):
        with pytest.raises(Forbidden):
            await authorise(firm.auth(kevin), write, resource)
    # A staff member on the team holds them (the refusal is the reach's, not the action's).
    teammate = await firm.person(lines=("tax",))
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        firm.tenant_id,
        tax.id,
        teammate.user_id,
    )
    await authorise(firm.auth(teammate), "request_item.mark_ready", resource)


async def test_ac23_never_audit_never_an_attest_client(firm: Firm) -> None:
    kevin = await firm.person(lines=("tax", "audit"))
    await _set(firm, "tax")
    audit = await firm.engagement(kind="fs_audit")
    attest_client = await firm.engagement()  # a tax engagement on a client …
    other = await firm.engagement(attest_client.client_id, kind="tax_compliance")
    await firm.seed.attest(firm.tenant_id, other.id)  # … that is an attest client
    plain = await firm.engagement()
    assert await _reads(firm, kevin, plain)
    assert not await _reads(firm, kevin, audit)
    assert not await _reads(firm, kevin, attest_client)
    listed = await _listed(firm, kevin)
    assert plain.id in listed
    assert not {audit.id, attest_client.id, other.id} & listed


async def test_ac23_never_a_walled_client_an_offshore_member_or_an_admin(firm: Firm) -> None:
    await _set(firm, "tax")
    tax = await firm.engagement()
    kevin = await firm.person(lines=("tax",))
    remy = await firm.person(lines=("tax",), offshore=True)
    ada = await firm.person("firm_admin", level="admin", lines=("tax",))
    felix = await firm.person("security_admin", level="admin", lines=("tax",))
    ops = await firm.person(level="admin", lines=("tax",))
    assert await _reads(firm, kevin, tax)
    margaret = await firm.person(level="partner")
    wall = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {
            "user_id": str(kevin.user_id),
            "client_id": str(tax.client_id),
            "reason_code": "relative",
            "approver_user_id": str(margaret.user_id),
        },
    )
    assert wall.status_code == 201, wall.text
    walled = await firm.call("GET", f"/v1/engagements/{tax.id}", kevin)
    assert walled.status_code == 404
    assert walled.json() == {"detail": "not found"}
    assert tax.id not in await _listed(firm, kevin)
    assert not await _reads(firm, remy, tax)
    assert tax.id not in await _listed(firm, remy)
    assert not await _reads(firm, ops, tax)
    # Admins keep metadata (ADR-024) but the line gives them no content.
    for admin in (ada, felix):
        items = await firm.call("GET", f"/v1/engagements/{tax.id}/request-items", admin)
        assert items.status_code in (403, 404), items.text
        assert tax.marker not in items.text


async def test_ac22_lists_agree_with_authorise_for_every_principal(firm: Firm) -> None:
    await _set(firm, "tax")
    await _set(firm, "cas")
    engagements = [
        await firm.engagement(),
        await firm.engagement(kind="cas_monthly_close"),
        await firm.engagement(kind="advisory"),
        await firm.engagement(kind="fs_audit"),
    ]
    attest = await firm.engagement()
    await firm.seed.attest(firm.tenant_id, (await firm.engagement(attest.client_id)).id)
    engagements.append(attest)
    people = [
        await firm.person(lines=("tax",)),
        await firm.person(lines=("cas", "advisory")),
        await firm.person(lines=("tax",), offshore=True),
        await firm.person(level="admin", lines=("tax",)),
        await firm.person(),
        # Security review M1 (DEC-383): people on the tax line holding a team role on the tax
        # engagement that the read is not granted to; ADR-183 rule 6 says the team role decides.
        await firm.person(lines=("tax",)),
        await firm.person(lines=("tax",)),
        await firm.person(lines=("tax",)),
    ]
    for who, role in zip(
        people[5:], ("client_service", "specialist", "eqr_reviewer"), strict=True
    ):
        await firm.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            firm.tenant_id,
            engagements[0].id,
            who.user_id,
            role,
        )
    tenant = TenantContext(firm.tenant_id, "human", "probe")
    for who in people:
        allowed: set[uuid.UUID] = set()
        for engagement in engagements:
            resource = await engagement_resource(tenant, engagement.id)
            try:
                await authorise(firm.auth(who), "request_item.read", resource)
                allowed.add(engagement.id)
            except Forbidden:
                pass
        listed = await _listed(firm, who) & {e.id for e in engagements}
        assert listed == allowed, (who.user_id, listed, allowed)
    # Kevin (tax) reaches exactly the plain tax engagement; the second person CAS only (advisory
    # stays "Engagement team only").
    assert await _listed(firm, people[0]) & {e.id for e in engagements} == {engagements[0].id}
    assert await _listed(firm, people[1]) & {e.id for e in engagements} == {engagements[1].id}


async def test_ac24_another_firms_policy_reaches_nothing_here(firm: Firm, net: Net) -> None:
    other = await _firm(net)
    await _set(other, "tax")
    ours = await firm.engagement()
    kevin = await firm.person(lines=("tax",))
    assert not await _reads(firm, kevin, ours)
    assert (await _lines(firm))["tax"]["version"] == 0
    # Their line member never reaches our engagement either.
    theirs = await other.person(lines=("tax",))
    for path in (f"/v1/engagements/{ours.id}", f"/v1/engagements/{ours.id}/request-items"):
        response = await other.call("GET", path, theirs)
        assert response.status_code == 404, response.text
    # Nor does their admin change our policy.
    cross = await other.call("PUT", f"{LINES}/tax", other.grace, _policy(1))
    assert cross.status_code in (200, 409), cross.text  # their own row, never ours
    assert (await _lines(firm))["tax"]["content_visible_to"] == "engagement_team_only"


# ================================================================================================
# Annual independence (AC6.1 to AC6.3; SPEC-024 AC-10 to AC-12; DEC-381)
# ================================================================================================


async def _publish(firm: Firm, text: str = "I am independent of every client.") -> int:
    with clock.frozen(MID_YEAR):
        saved = _body(await firm.call("PUT", STATEMENT, firm.grace, {"body": text}), 200, 201)
    return cast(int, saved["version"])


async def _answer(
    firm: Firm, who: Person, decision: str = "confirmed", **extra: object
) -> httpx.Response:
    body: Json = {"year": 2026, "decision": decision, "statement_version": 1, **extra}
    with clock.frozen(MID_YEAR):
        return await firm.call("POST", MINE, who, body)


async def _year(firm: Firm, who: Person) -> httpx.Response:
    with clock.frozen(MID_YEAR):
        return await firm.call("GET", f"{ANNUAL}?year=2026", who)


async def test_ac6_1_kevin_confirms_the_published_statement_for_himself_only(firm: Firm) -> None:
    kevin = await firm.person()
    before = await _answer(firm, kevin)
    assert before.status_code == 409, before.text
    assert _detail(before) == "independence_statement_missing"
    stale_publish = await firm.call("PUT", STATEMENT, firm.grace, {"body": "Statement"}, mfa=False)
    assert stale_publish.status_code == 403, stale_publish.text
    version = await _publish(firm)
    with clock.frozen(MID_YEAR):
        mine = _body(await firm.call("GET", MINE, kevin))
    assert (mine["year"], mine["status"]) == (2026, "not_yet")
    assert cast(Json, mine["statement"])["version"] == version
    confirmed = _body(await _answer(firm, kevin), 201)
    assert (confirmed["year"], confirmed["decision"]) == (2026, "confirmed")
    rows = await firm.seed.rows(
        "SELECT user_id, decision, statement_version, actor_kind FROM "
        "independence_annual_confirmations WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert [tuple(r) for r in rows] == [(kevin.user_id, "confirmed", version, "human")]
    assert [r["actor_id"] for r in await firm.audit("independence.annual_confirmed")] == [
        str(kevin.user_id)
    ]
    assert len(await firm.outbox("independence.annual_recorded")) == 1
    assert await has_current_annual_confirmation(
        TenantContext(firm.tenant_id, "human", "p"), kevin.user_id, date(2026, 6, 15)
    )


async def test_ac6_3_nobody_confirms_for_someone_else_the_body_has_no_user_id(
    firm: Firm,
) -> None:
    kevin = await firm.person()
    await _publish(firm)
    for field in ("user_id", "for_user_id", "on_behalf_of"):
        for_kevin = await _answer(firm, firm.grace, **{field: str(kevin.user_id)})
        assert for_kevin.status_code == 422, (field, for_kevin.text)
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM independence_annual_confirmations WHERE tenant_id = $1",
            firm.tenant_id,
        )
        == 0
    )
    # Grace's own answer is hers, never Kevin's.
    assert (await _answer(firm, firm.grace)).status_code == 201
    tenant = TenantContext(firm.tenant_id, "human", "p")
    assert not await has_current_annual_confirmation(tenant, kevin.user_id, date(2026, 6, 15))
    assert await has_current_annual_confirmation(tenant, firm.grace.user_id, date(2026, 6, 15))


async def test_ac6_1_a_decline_needs_a_note_and_only_the_current_year_is_answered(
    firm: Firm,
) -> None:
    kevin = await firm.person()
    await _publish(firm)
    for note in (None, "", "   "):
        extra: Json = {} if note is None else {"note": note}
        bare = await _answer(firm, kevin, "declined", **extra)
        assert bare.status_code == 422, (note, bare.text)
        if note is None:
            assert _detail(bare) == "annual_confirmation_invalid"
    for year in (2025, 2027):
        with clock.frozen(MID_YEAR):
            wrong = await firm.call(
                "POST",
                MINE,
                kevin,
                {"year": year, "decision": "confirmed", "statement_version": 1},
            )
        assert wrong.status_code == 422, (year, wrong.text)
        assert _detail(wrong) == "annual_confirmation_invalid"
    declined = await _answer(firm, kevin, "declined", note="My spouse holds Ashford stock.")
    assert declined.status_code == 201, declined.text
    tenant = TenantContext(firm.tenant_id, "human", "p")
    assert not await has_current_annual_confirmation(tenant, kevin.user_id, date(2026, 6, 15))
    assert [r["actor_id"] for r in await firm.audit("independence.annual_declined")] == [
        str(kevin.user_id)
    ]
    # SPEC-024 AC-12: the newest answer wins.
    assert (await _answer(firm, kevin)).status_code == 201
    assert await has_current_annual_confirmation(tenant, kevin.user_id, date(2026, 6, 15))
    assert (await _answer(firm, kevin, "declined", note="Changed again.")).status_code == 201
    assert not await has_current_annual_confirmation(tenant, kevin.user_id, date(2026, 6, 15))
    # Another year's question reads its own answers (none).
    assert not await has_current_annual_confirmation(tenant, kevin.user_id, date(2027, 6, 15))


async def test_ac10_a_newer_statement_makes_the_old_version_stale(firm: Firm) -> None:
    kevin = await firm.person()
    assert await _publish(firm, "Version one.") == 1
    assert await _publish(firm, "Version two.") == 2
    stale = await _answer(firm, kevin)  # names version 1
    assert stale.status_code == 409, stale.text
    assert _detail(stale) == "stale_version"
    fresh = await _answer(firm, kevin, statement_version=2)
    assert fresh.status_code == 201, fresh.text


async def test_ac10_confirmations_are_insert_only_and_human_only_in_the_database(
    firm: Firm, migrated_db: Migrated
) -> None:
    kevin = await firm.person()
    await _publish(firm)
    assert (await _answer(firm, kevin)).status_code == 201
    app_role = Seeder(migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://"))
    for sql in (
        "UPDATE independence_annual_confirmations SET decision = 'declined'",
        "DELETE FROM independence_annual_confirmations",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app_role.run(sql)
    # As an agent acting with Kevin's id, through the app's own session (DEC-383's own-row
    # trigger passes), so only the actor-kind CHECK can refuse.
    with pytest.raises(IntegrityError) as raised:
        async with tenant_session(
            TenantContext(firm.tenant_id, "agent", str(kevin.user_id))
        ) as session:
            await session.execute(
                text(
                    "INSERT INTO independence_annual_confirmations (tenant_id, user_id, year, "
                    "decision, statement_version) VALUES (:t, :u, 2026, 'confirmed', 1)"
                ),
                {"t": firm.tenant_id, "u": kevin.user_id},
            )
    assert getattr(raised.value.orig, "sqlstate", None) == CHECK_VIOLATION


async def test_ac10_agents_the_system_and_client_users_never_confirm(firm: Firm) -> None:
    await _publish(firm)
    site = await firm.seed.site(firm.tenant_id, firm.grace.user_id, "Ashford")
    contact = await firm.seed.client_contact(site)
    refused = await _answer(firm, contact)
    assert refused.status_code in (403, 404), refused.text
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM independence_annual_confirmations WHERE tenant_id = $1",
            firm.tenant_id,
        )
        == 0
    )
    decisions = RULES["independence.annual_confirm"].decisions
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", principal


async def test_ac6_3_the_years_list_foots_for_readers_and_404s_for_everyone_else(
    firm: Firm,
) -> None:
    await _publish(firm)
    daniel = await firm.person(level="partner")
    quinn = await firm.person("quality_partner", level="manager")
    kevin = await firm.person()
    lena = await firm.person(level="seasonal")
    gone = await firm.person()
    await firm.seed.revoke(gone)
    felix = await firm.person("security_admin", level="admin")
    assert (await _answer(firm, kevin)).status_code == 201
    assert (await _answer(firm, lena, "declined", note="Family at Ashford.")).status_code == 201
    for reader in (firm.grace, daniel, quinn):
        page = _body(await _year(firm, reader))
        rows = {cast(str, r["user_id"]): r for r in cast(list[Json], page["rows"])}
        assert str(gone.user_id) not in rows  # active staff only
        assert {str(kevin.user_id), str(lena.user_id), str(daniel.user_id)} <= set(rows)
        assert rows[str(kevin.user_id)]["status"] == "confirmed"
        assert rows[str(kevin.user_id)]["decided_at"] is not None
        assert rows[str(lena.user_id)]["status"] == "declined"
        assert rows[str(lena.user_id)]["note"] == "Family at Ashford."
        assert rows[str(daniel.user_id)]["status"] == "not_yet"
        counts = cast(dict[str, int], page["counts"])
        assert counts == {
            "confirmed": len([r for r in rows.values() if r["status"] == "confirmed"]),
            "not_yet": len([r for r in rows.values() if r["status"] == "not_yet"]),
            "declined": len([r for r in rows.values() if r["status"] == "declined"]),
        }
        assert sum(counts.values()) == len(rows)
        assert (counts["confirmed"], counts["declined"]) == (1, 1)
    for outsider in (kevin, felix):
        refused = await _year(firm, outsider)
        assert refused.status_code == 404, refused.text


async def test_ac12_another_firm_reads_nothing_of_this_firms_answers(firm: Firm, net: Net) -> None:
    other = await _firm(net)
    kevin = await firm.person()
    await _publish(firm, "Ours.")
    assert (await _answer(firm, kevin)).status_code == 201
    # Kevin's answer is this firm's: the other firm's reader neither lists nor counts it.
    page = _body(await _year(other, other.grace))
    assert str(kevin.user_id) not in json.dumps(page)
    assert cast(dict[str, int], page["counts"]).get("confirmed", 0) == 0
    assert not await has_current_annual_confirmation(
        TenantContext(other.tenant_id, "human", "p"), kevin.user_id, date(2026, 6, 15)
    )
    # Their statement is theirs: none published there yet.
    with clock.frozen(MID_YEAR):
        theirs = await other.call("GET", STATEMENT, other.grace)
    assert "Ours." not in theirs.text
    with clock.frozen(MID_YEAR):
        cross = await other.call(
            "POST",
            MINE,
            other.grace,
            {"year": 2026, "decision": "confirmed", "statement_version": 1},
        )
    assert cross.status_code == 409, cross.text  # their firm has no statement
    assert _detail(cross) == "independence_statement_missing"


# ================================================================================================
# The access-end job (G-01 AC4.5; SPEC-024 AC-9; DEC-381)
# ================================================================================================


async def _season(firm: Firm, count: int = 5) -> list[Person]:
    seasonal = [await firm.person(level="seasonal") for _ in range(count)]
    with clock.frozen(_ct(date(2026, 10, 20), 12)):
        saved = _body(
            await firm.call(
                "PUT",
                "/v1/firm/groups/seasonal/access-ends",
                firm.grace,
                {"access_ends_on": OCT_31.isoformat()},
            )
        )
    assert saved["members"] == count
    return seasonal


async def _sweep(instant: datetime) -> None:
    with clock.frozen(instant):
        await sweep_access_ends_activity()


async def test_ac4_5_after_the_firms_midnight_the_five_end_on_behalf_of_grace(
    firm: Firm,
) -> None:
    kevin = await firm.person()
    seasonal = await _season(firm)
    with clock.frozen(_ct(date(2026, 10, 25), 9)):
        tallies = _body(await firm.call("GET", STAFF, firm.grace))["tallies"]
    used_before = cast(Json, tallies)["seats_used"]
    await _sweep(_ct(OCT_31, 23, 50))  # the last day of access: still on
    for who in seasonal:
        assert (await firm.membership(who))["status"] == "active"
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    for who in seasonal:
        row = await firm.membership(who)
        assert (row["status"], row["revoked_reason"], row["revoked_on_behalf_of"]) == (
            "revoked",
            "access_ended",
            firm.grace.user_id,
        )
    assert (await firm.membership(kevin))["status"] == "active"
    rows = await firm.audit("membership.deactivated")
    assert len(rows) == 5
    assert {(r["actor_kind"], r["on_behalf_of_user_id"]) for r in rows} == {
        ("system", firm.grace.user_id)
    }
    assert len(await firm.outbox("membership.deactivated")) == 5
    for who in seasonal:
        assert await firm.access_changed_for(who) >= 1
    # ADM-02e on Nov 2: five deactivated rows and five seats freed.
    with clock.frozen(_ct(date(2026, 11, 2), 9)):
        listed = _body(await firm.call("GET", STAFF, firm.grace))
        person = _body(await firm.call("GET", f"{STAFF}/{seasonal[0].user_id}", firm.grace))
    assert cast(Json, listed["tallies"])["seats_used"] == cast(int, used_before) - 5
    assert cast(Json, person["row"])["status"] == "deactivated"


async def test_ac4_5_adm02e_reads_deactivated_on_the_last_day_of_access(firm: Firm) -> None:
    """AC4.5: on Nov 2 ADM-02e shows "Deactivated Oct 31" for each."""
    seasonal = await _season(firm, 1)
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    with clock.frozen(_ct(date(2026, 11, 2), 9)):
        person = _body(await firm.call("GET", f"{STAFF}/{seasonal[0].user_id}", firm.grace))
    assert cast(Json, person["row"])["deactivated_on"] == OCT_31.isoformat()


async def test_ac4_5_a_rerun_changes_nothing(firm: Firm) -> None:
    seasonal = await _season(firm)
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    audit = len(await firm.audit("membership.deactivated"))
    outbox = len(await firm.outbox("membership.deactivated"))
    for instant in (_ct(date(2026, 11, 1), 1, 20), _ct(date(2026, 11, 2), 0, 20)):
        await _sweep(instant)
    assert len(await firm.audit("membership.deactivated")) == audit == 5
    assert len(await firm.outbox("membership.deactivated")) == outbox == 5
    for who in seasonal:
        assert (await firm.membership(who))["status"] == "revoked"


async def test_ac4_5_a_moved_date_is_respected_and_the_newest_setter_is_named(
    firm: Firm,
) -> None:
    seasonal = await _season(firm)
    ada = await firm.person("firm_admin", level="admin")
    moved = seasonal[0]
    with clock.frozen(_ct(date(2026, 10, 25), 9)):
        person = _body(await firm.call("GET", f"{STAFF}/{moved.user_id}", ada))
        patched = await firm.call(
            "PATCH",
            f"{STAFF}/{moved.user_id}",
            ada,
            {"version": person["version"], "access_ends_on": "2026-11-30"},
        )
    assert patched.status_code == 200, patched.text
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    assert (await firm.membership(moved))["status"] == "active"
    for who in seasonal[1:]:
        assert (await firm.membership(who))["revoked_on_behalf_of"] == firm.grace.user_id
    await _sweep(_ct(date(2026, 11, 30), 22))
    assert (await firm.membership(moved))["status"] == "active"
    await _sweep(_ct(date(2026, 12, 1), 0, 20))
    row = await firm.membership(moved)
    assert (row["status"], row["revoked_reason"], row["revoked_on_behalf_of"]) == (
        "revoked",
        "access_ended",
        ada.user_id,
    )


async def test_ac4_5_the_day_is_the_firms_own_time_zone(net: Net) -> None:
    pacific = await _firm(net, "America/Los_Angeles")
    [lena] = await _season(pacific, 1)
    # 06:30 UTC on Nov 1 is already Nov 1 in Chicago, still Oct 31 in Los Angeles.
    await _sweep(datetime(2026, 11, 1, 6, 30, tzinfo=UTC))
    assert (await pacific.membership(lena))["status"] == "active"
    await _sweep(datetime(2026, 11, 1, 8, 30, tzinfo=UTC))  # 00:30 or 01:30 Pacific on Nov 1
    assert (await pacific.membership(lena))["status"] == "revoked"


async def test_ac4_5_seven_days_ahead_firm_admins_are_told_once_per_date(firm: Firm) -> None:
    await _season(firm)
    await _sweep(_ct(date(2026, 10, 23), 12))  # eight days ahead
    assert await firm.outbox("membership.access_ending") == []
    await _sweep(_ct(date(2026, 10, 24), 0, 20))
    for instant in (_ct(date(2026, 10, 24), 5), _ct(date(2026, 10, 28), 9), _ct(OCT_31, 12)):
        await _sweep(instant)
    assert len(await firm.outbox("membership.access_ending")) == 1
    assert len(await firm.audit("membership.access_ending_notified")) == 1
    # A second date gets its own single notice.
    late = await firm.person(level="seasonal", ends=date(2026, 11, 20))
    await _sweep(_ct(date(2026, 11, 14), 9))
    await _sweep(_ct(date(2026, 11, 15), 9))
    assert len(await firm.outbox("membership.access_ending")) == 2
    assert (await firm.membership(late))["status"] == "active"


async def test_spec024_ac9_the_last_firm_and_security_admins_are_never_ended(
    firm: Firm,
) -> None:
    felix = await firm.person("security_admin", level="admin")
    for who in (firm.grace, felix):
        await firm.seed.run(
            "UPDATE memberships SET access_ends_on = $3 WHERE tenant_id = $1 AND user_id = $2",
            firm.tenant_id,
            who.user_id,
            OCT_31,
        )
    seasonal = await _season(firm, 1)
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    assert (await firm.membership(firm.grace))["status"] == "active"
    assert (await firm.membership(felix))["status"] == "active"
    assert (await firm.membership(seasonal[0]))["status"] == "revoked"


async def test_ac4_5_another_firms_members_are_untouched_by_this_firms_date(
    firm: Firm, net: Net
) -> None:
    other = await _firm(net)
    theirs = await other.person(level="seasonal", ends=date(2026, 12, 31))
    await _season(firm, 2)
    await _sweep(_ct(date(2026, 11, 1), 0, 20))
    assert (await other.membership(theirs))["status"] == "active"
    assert await other.audit("membership.deactivated") == []
    assert await other.outbox("membership.access_ending") == []


# ================================================================================================
# INV-1: agent and system refused on every new write (contract §2, §5)
# ================================================================================================


async def test_inv1_agent_and_system_are_refused_every_new_write(firm: Firm) -> None:
    agent = firm.agent(NEW_WRITES)
    for action in NEW_WRITES:
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, decisions)
        with pytest.raises(Forbidden):
            await authorise(agent, action, Resource.firm(firm.tenant_id))
    read = RULES["independence.annual_read"].decisions
    assert (read.get("agent", "deny"), read.get("system", "deny")) == ("deny", "deny")
