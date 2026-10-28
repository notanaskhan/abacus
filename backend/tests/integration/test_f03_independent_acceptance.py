"""F-03-T34: independent acceptance tests (ADR-078) for entitlements, `/v1/me` and
`/v1/me/capabilities`, the list envelope and work-item subtype cardinality, against Postgres.

Written from the plan and the contracts, not from the code: F-03 stories 1.1, 6.1, 6.2, 7.1 and
8.1, §4.3 and §4.6; SPEC-047 AC-11 and AC-14; `docs/contracts/work-items.md` (C1 v1); ADR-145,
ADR-147, ADR-148; DEC-129. "Tests … cover every field of the Me contract and every cardinality
rule, and pass on main." Where the code does not yet meet the plan, the test is a strict xfail
naming the gap (never weakened).

Seeding runs as the superuser; every behaviour under test runs as the app role, through
`tenant_session` (the services) or `create_app()` (HTTP).
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast

import httpx
import pytest
from fastapi import Depends
from pydantic import BaseModel

import abacus.api.app as app_module
import abacus.modules.closes.api
import abacus.modules.notices.api
import abacus.modules.tax.api  # each registers its work-item kind
from abacus.api import create_app
from abacus.kernel import _flags
from abacus.kernel.clock import today as business_today
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.api import create_work_item
from abacus.modules.identity.api import (
    OWN,
    AbacusRouter,
    AgentContext,
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    configure_verifier,
    engagement_resource,
    reset_verifier,
)
from abacus.modules.identity.authz import recording_checks
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)
from abacus.modules.identity.service import TENANT_HEADER
from abacus.modules.platform.api import Entitlement, require_entitlement
from abacus.modules.platform.capabilities import capabilities
from abacus_tools.codegen import feature_flags
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api and abacus.modules.notices.api and abacus.modules.tax.api

Json = dict[str, Any]  # parsed JSON response bodies, untyped by httpx
# The six entitlement modules (ADR-148; F-03 §3.7, migration 0088).
MODULES = (
    "attest",
    "internal_audit",
    "group_audit",
    "statements_studio",
    "office_addins",
    "insights",
)
# The attest families hold one assurance work item from creation (C1 §1).
ATTEST_TYPES = (
    "fs_audit",
    "ebp_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
    "readiness",
    "internal_audit",
)
NON_ATTEST_TYPES = ("tax_compliance", "cas_monthly_close", "notice_response", "advisory")
_IDENTIFIER = re.compile(r"^(?:[a-z][a-z0-9_]*|G[1-9]|[0-9a-f-]{36}|-?[0-9]+)$")


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    """Each test runs on its own event loop: fresh pools, pointed at the app and identity roles."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


class Held(BaseModel):
    seats: int | None


probe = AbacusRouter(prefix="/probe-f03", tags=["probe"])


@probe.get("/attest", action=OWN, response_model=Held)
async def _attest_only(
    held: Annotated[Entitlement, Depends(require_entitlement("attest"))],
) -> Held:
    return Held(seats=held.seats)


@pytest.fixture
async def http(
    idp: FakeIdentityProvider, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(app_module, "ROUTERS", (*app_module.ROUTERS, probe))
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- a synthetic Brightwater Hale-shaped firm ----------------------------------------------------


@dataclass(frozen=True)
class Who:
    user_id: uuid.UUID
    subject: str
    tenant_id: uuid.UUID

    def context(self) -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant_id, "human", str(self.user_id)),
            self.user_id,
            uuid.uuid4(),
            None,
            datetime.now(UTC) - timedelta(minutes=1),
        )


class Firm:
    """One firm per test (tests share the database, so every name is unique to its tenant)."""

    def __init__(self, seed: Seeder, tz: str = "America/Denver") -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.tz = tz
        self.office: uuid.UUID | None = None

    async def make(self) -> Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name, time_zone) "
            "VALUES ($1, 'Brightwater Hale LLP', $2)",
            self.tenant,
            self.tz,
        )
        self.office = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO offices (tenant_id, name, time_zone) "
                "VALUES ($1, 'Denver', 'America/Denver') RETURNING id",
                self.tenant,
            ),
        )
        return self

    async def person(self, display: str, *, kind: str = "staff", office: bool = True) -> Who:
        subject = f"f03-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                ISSUER,
                subject,
                f"{subject}@example.test",
                display,
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, office_id) "
            "VALUES ($1, $2, 'active', $3, $4)",
            self.tenant,
            user_id,
            kind,
            self.office if office and kind == "staff" else None,
        )
        return Who(user_id, subject, self.tenant)

    async def client(self, name: str, entities: list[str]) -> tuple[uuid.UUID, list[uuid.UUID]]:
        client = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                self.tenant,
                name,
            ),
        )
        ids = [
            cast(
                uuid.UUID,
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) "
                    "VALUES ($1, $2, $3) RETURNING id",
                    self.tenant,
                    client,
                    entity,
                ),
            )
            for entity in entities
        ]
        return client, ids

    async def engagement(
        self,
        client: uuid.UUID,
        entity: uuid.UUID,
        type_: str,
        created_by: Who,
        *,
        name: str = "2026",
        status: str = "active",
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, type, "
                "status, fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, $5, $6, '2026-01-01', '2026-12-31', $7) RETURNING id",
                self.tenant,
                client,
                entity,
                name,
                type_,
                status,
                created_by.user_id,
            ),
        )

    async def member(self, engagement: uuid.UUID, who: Who, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            who.user_id,
            role,
        )

    async def entitle(
        self,
        module: str,
        *,
        enabled: bool = True,
        valid_from: date | None = None,
        valid_to: date | None = None,
    ) -> None:
        today = await business_today(TenantContext(self.tenant, "human", "probe"))
        await self.seed.run(
            "INSERT INTO tenant_entitlements (tenant_id, module, enabled, seats, "
            "agent_minutes_allowance, valid_from, valid_to, set_by) "
            "VALUES ($1, $2, $3, 12, 600, $4, $5, 'operator:probe')",
            self.tenant,
            module,
            enabled,
            valid_from or today,
            valid_to,
        )

    async def count(self, sql: str, *args: object) -> int:
        return int(cast(int, await self.seed.value(sql, *args)))


def _auth(idp: FakeIdentityProvider, who: Who, *, mfa: bool = False) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {idp.token(who.subject, mfa=mfa)}",
        TENANT_HEADER: str(who.tenant_id),
    }


async def _staffed(seed: Seeder, type_: str, client_name: str) -> tuple[Firm, Who, uuid.UUID]:
    """A firm, its engagement partner (Priya Raman's role) and one engagement of `type_`."""
    firm = await Firm(seed).make()
    partner = await firm.person("Priya Raman")
    client, (entity,) = await firm.client(client_name, [client_name])
    engagement = await firm.engagement(client, entity, type_, partner)
    await firm.member(engagement, partner, "engagement_partner")
    return firm, partner, engagement


# ================================================================================================
# Work-item subtypes and their cardinality (Story 1.1; SPEC-047 AC-11; C1 §1 and §6)
# ================================================================================================


async def test_ac11_copperleaf_holds_twelve_closes_and_a_thirteenth_for_a_period_is_409(
    seed: Seeder,
) -> None:
    firm, priya, close_engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    ctx = priya.context()
    periods = [f"2026-{month:02d}" for month in range(1, 13)]
    for period in periods:
        await create_work_item(
            ctx, close_engagement, "close", name=period, details={"period": period}
        )

    rows = await seed.rows(
        "SELECT w.id, w.tenant_id, w.engagement_id, c.tenant_id AS c_tenant, "
        "c.engagement_id AS c_engagement, c.period FROM work_items w "
        "JOIN closes c ON c.work_item_id = w.id WHERE w.engagement_id = $1 AND w.kind = 'close'",
        close_engagement,
    )
    assert sorted(r["period"] for r in rows) == periods
    for row in rows:  # every subtype row carries (tenant_id, engagement_id, work_item_id)
        assert (row["c_tenant"], row["c_engagement"]) == (firm.tenant, close_engagement)

    with pytest.raises(Exception) as refused:
        await create_work_item(
            ctx, close_engagement, "close", name="2026-03 again", details={"period": "2026-03"}
        )
    error = refused.value
    assert getattr(error, "code", None) == "work_item_exists"  # C1 §6 (409)
    assert getattr(error, "facts", None) == {"kind": "close"}
    assert (
        await firm.count(
            "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'close'",
            close_engagement,
        )
        == 12
    )  # the refused close left no work item behind
    assert (
        await firm.count(
            "SELECT count(*) FROM audit_events "
            "WHERE tenant_id = $1 AND action = 'work_item.created'",
            firm.tenant,
        )
        == 12
    )


async def test_ac11_a_period_is_unique_per_engagement_not_per_firm(seed: Seeder) -> None:
    firm, priya, first = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    client, (entity,) = await firm.client("Copperleaf Logistics", ["Copperleaf Logistics"])
    second = await firm.engagement(client, entity, "cas_monthly_close", priya)
    await firm.member(second, priya, "engagement_partner")
    for engagement in (first, second):
        await create_work_item(
            priya.context(), engagement, "close", name="Jan", details={"period": "2026-01"}
        )
    assert (
        await firm.count(
            "SELECT count(*) FROM closes WHERE tenant_id = $1 AND period = '2026-01'", firm.tenant
        )
        == 2
    )


async def test_ac11_a_second_assurance_item_on_an_fs_audit_engagement_is_409(seed: Seeder) -> None:
    firm, partner, audit = await _staffed(seed, "fs_audit", "Northwind")
    with pytest.raises(Exception) as refused:
        await create_work_item(
            partner.context(), audit, "assurance", name="Second", details={"assurance_type": "x"}
        )
    assert getattr(refused.value, "code", None) == "work_item_exists"
    assert getattr(refused.value, "facts", None) == {"kind": "assurance"}
    assert (
        await firm.count(
            "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            audit,
        )
        == 1
    )


@pytest.mark.parametrize("type_", ATTEST_TYPES)
async def test_ac11_every_attest_engagement_starts_with_one_assurance_item(
    seed: Seeder, type_: str
) -> None:
    firm, _, engagement = await _staffed(seed, type_, "Bluestem")
    kinds = await seed.rows("SELECT kind FROM work_items WHERE engagement_id = $1", engagement)
    assert [r["kind"] for r in kinds] == ["assurance"]
    assert (
        await firm.count(
            "SELECT count(*) FROM assurance_work_items WHERE engagement_id = $1", engagement
        )
        == 1
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM engagement_entities "
            "WHERE engagement_id = $1 AND role = 'primary'",
            engagement,
        )
        == 1
    )


@pytest.mark.parametrize("type_", NON_ATTEST_TYPES)
async def test_ac11_a_non_attest_engagement_has_a_primary_entity_and_no_assurance_item(
    seed: Seeder, type_: str
) -> None:
    firm, _, engagement = await _staffed(seed, type_, "Meridian")
    assert (
        await firm.count("SELECT count(*) FROM work_items WHERE engagement_id = $1", engagement)
        == 0
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM engagement_entities "
            "WHERE engagement_id = $1 AND role = 'primary'",
            engagement,
        )
        == 1
    )


async def test_ac11_thornbury_four_returns_across_the_decedent_and_the_estate(
    seed: Seeder,
) -> None:
    firm = await Firm(seed).make()
    partner = await firm.person("Daniel Reyes")
    client, (decedent, estate) = await firm.client(
        "Thornbury", ["Harold Thornbury (decedent)", "Estate of Harold Thornbury"]
    )
    engagement = await firm.engagement(client, decedent, "tax_compliance", partner)
    await firm.member(engagement, partner, "engagement_partner")
    returns = [
        (decedent, "1040", 2025),
        (decedent, "706", 2025),
        (estate, "1041", 2025),
        (estate, "1041", 2026),
    ]
    for entity, form, year in returns:
        await create_work_item(
            partner.context(),
            engagement,
            "tax_return",
            name=f"{form} {year}",
            client_entity_id=entity,
            details={"form": form, "tax_year": year},
        )
    rows = await seed.rows(
        "SELECT w.client_entity_id AS w_entity, t.client_entity_id, t.form, t.tax_year "
        "FROM work_items w JOIN tax_returns t ON t.work_item_id = w.id "
        "WHERE w.engagement_id = $1",
        engagement,
    )
    assert sorted((r["client_entity_id"], r["form"], r["tax_year"]) for r in rows) == sorted(
        returns
    )
    assert all(r["w_entity"] == r["client_entity_id"] for r in rows)


async def test_kinds_without_a_cardinality_rule_take_more_than_one(seed: Seeder) -> None:
    firm, partner, engagement = await _staffed(seed, "notice_response", "Ridgeline")
    for _ in range(2):
        await create_work_item(
            partner.context(),
            engagement,
            "notice",
            name="CP2000",
            details={"notice_code": "CP2000", "received_on": date(2026, 9, 1)},
        )
        await create_work_item(
            partner.context(),
            engagement,
            "advisory_project",
            name="Entity review",
            details={"name": "Entity review"},
        )
    assert (
        await firm.count("SELECT count(*) FROM notices WHERE engagement_id = $1", engagement) == 2
    )
    assert (
        await firm.count(
            "SELECT count(*) FROM advisory_projects WHERE engagement_id = $1", engagement
        )
        == 2
    )


async def test_an_unregistered_kind_is_409_and_writes_nothing(seed: Seeder) -> None:
    firm, partner, engagement = await _staffed(seed, "advisory", "Ridgeline")
    with pytest.raises(Exception) as refused:
        await create_work_item(partner.context(), engagement, "binder", name="Not a kind")
    assert getattr(refused.value, "code", None) == "unknown_work_item_kind"
    assert (
        await firm.count("SELECT count(*) FROM work_items WHERE engagement_id = $1", engagement)
        == 0
    )


@pytest.mark.parametrize("role", ["engagement_partner", "manager"])
async def test_work_item_create_is_allowed_to_partner_and_manager(seed: Seeder, role: str) -> None:
    firm, partner, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    who = partner if role == "engagement_partner" else await firm.person("Manager")
    if role == "manager":
        await firm.member(engagement, who, "manager")
    await create_work_item(
        who.context(), engagement, "close", name="Feb", details={"period": "2026-02"}
    )


async def test_work_item_create_is_denied_below_manager_and_to_an_agent(seed: Seeder) -> None:
    firm, partner, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    senior = await firm.person("Senior")
    await firm.member(engagement, senior, "senior")
    with pytest.raises(Forbidden):
        await create_work_item(
            senior.context(), engagement, "close", name="Jan", details={"period": "2026-01"}
        )
    # C1 §2: `work_item.create` is denied to the agent, even with the action in its task scope
    # and a partner as the person it acts for (INV-1).
    run = uuid.uuid4()
    agent = AgentContext(
        tenant=TenantContext(firm.tenant, "agent", f"agent:probe:{run}", partner.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=engagement,
        task_scope=frozenset({"work_item.create"}),
        initiator=partner.context(),
        issued_by=_ISSUER,
    )
    with pytest.raises(Forbidden):
        await authorise(
            agent, "work_item.create", await engagement_resource(agent.tenant, engagement)
        )
    assert (
        await firm.count("SELECT count(*) FROM work_items WHERE engagement_id = $1", engagement)
        == 0
    )


async def test_another_firms_engagement_is_not_found(seed: Seeder) -> None:
    _, _, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    _, outsider, _ = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    with pytest.raises(NotFound):
        await create_work_item(
            outsider.context(), engagement, "close", name="Jan", details={"period": "2026-01"}
        )


# ================================================================================================
# Entitlements (Story 7.1; F-03-T28; ADR-148)
# ================================================================================================


async def test_story_7_1_a_route_guarded_by_attest_is_403_for_a_firm_without_it(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm = await Firm(seed).make()
    who = await firm.person("Rowan Achebe")
    response = await http.get("/probe-f03/attest", headers=_auth(idp, who))
    assert response.status_code == 403
    assert response.json() == {"detail": "entitlement_required", "facts": {"module": "attest"}}


async def test_story_7_1_the_same_route_answers_once_the_firm_holds_attest(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm = await Firm(seed).make()
    who = await firm.person("Rowan Achebe")
    await firm.entitle("attest")
    response = await http.get("/probe-f03/attest", headers=_auth(idp, who))
    assert response.status_code == 200
    assert response.json() == {"seats": 12}


@pytest.mark.parametrize("state", ["switched_off", "not_yet_valid", "lapsed"])
async def test_story_7_1_a_row_that_is_off_or_out_of_date_is_no_entitlement(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider, state: str
) -> None:
    firm = await Firm(seed).make()
    who = await firm.person("Rowan Achebe")
    today = await business_today(TenantContext(firm.tenant, "human", "probe"))
    if state == "switched_off":
        await firm.entitle("attest", enabled=False)
    elif state == "not_yet_valid":
        await firm.entitle("attest", valid_from=today + timedelta(days=1))
    else:
        await firm.entitle(
            "attest", valid_from=today - timedelta(days=60), valid_to=today - timedelta(days=1)
        )
    response = await http.get("/probe-f03/attest", headers=_auth(idp, who))
    assert response.status_code == 403
    assert response.json()["detail"] == "entitlement_required"


async def test_story_7_1_another_firms_entitlement_never_counts(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    holder = await Firm(seed).make()
    await holder.entitle("attest")
    firm = await Firm(seed).make()
    who = await firm.person("Rowan Achebe")
    response = await http.get("/probe-f03/attest", headers=_auth(idp, who))
    assert response.status_code == 403


async def test_story_7_1_no_module_is_a_flag() -> None:
    for name in _flags.FLAGS:
        assert not name.startswith("ff."), name
        assert name.split(".", 1)[0] not in MODULES, name
    for name in ("ff.attest", "attest.enabled", "insights.beta"):
        entry = (
            "flags:\n"
            f"  - name: {name}\n    description: probe\n    owner: builder\n"
            "    created: 2026-10-23\n    expires: 2026-12-01\n    kind: boolean\n"
            "    default: 'false'\n"
        )
        with pytest.raises(feature_flags.RegistryError):
            feature_flags.parse(entry)


# ================================================================================================
# /v1/me and /v1/me/capabilities (Story 6.2; SPEC-047 AC-14; §4.3; ADR-145, ADR-147)
# ================================================================================================

ME_FIELDS = frozenset(
    {"capabilities", "roles", "flags", "entitlements", "office_id", "tz"}
    | {"mfa_recent_until", "server_now", "portal"}
)


def _near_now(value: str) -> bool:
    moment = datetime.fromisoformat(value)
    return abs(moment - datetime.now(UTC)) < timedelta(minutes=5)


async def test_ac14_capabilities_carries_every_field_of_the_me_contract(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm = await Firm(seed, tz="America/Denver").make()
    who = await firm.person("Priya Raman")
    await firm.entitle("insights")
    await firm.entitle("attest", enabled=False)
    response = await http.get("/v1/me/capabilities", headers=_auth(idp, who))
    assert response.status_code == 200
    body: Json = response.json()
    assert set(body) >= ME_FIELDS
    offered = cast(list[object], body["capabilities"])
    assert all(isinstance(a, str) for a in offered)
    assert isinstance(body["roles"], list)
    assert body["office_id"] == str(firm.office)
    assert body["tz"] == "America/Denver"
    assert _near_now(body["server_now"])  # a real firm: no demo clock
    assert body["mfa_recent_until"] is None  # signed in without MFA
    assert body["portal"] is None  # a staff member has no portal shell
    assert body["entitlements"] == ["insights"]  # held modules only; attest is switched off
    assert set(body["flags"]) == set(_flags.FLAGS)
    # Every flag answers its value: a boolean, or a variant flag's string (P-07-T15 retired the
    # work-item list's flag this line once named).
    assert all(isinstance(v, bool | str) for v in cast(dict[str, object], body["flags"]).values())


async def test_ac14_mfa_recent_until_is_set_after_a_fresh_mfa(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm = await Firm(seed).make()
    who = await firm.person("Priya Raman")
    body: Json = (await http.get("/v1/me/capabilities", headers=_auth(idp, who, mfa=True))).json()
    until = datetime.fromisoformat(body["mfa_recent_until"])
    now = datetime.fromisoformat(body["server_now"])
    assert now < until <= now + timedelta(hours=1)


async def test_t30_grace_holloway_has_binder_and_invitation_actions_but_no_evidence_content(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, _, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    grace = await firm.person("Grace Holloway")
    await firm.member(engagement, grace, "client_service")
    response = await http.get(
        "/v1/me/capabilities",
        params={"engagement_id": str(engagement)},
        headers=_auth(idp, grace),
    )
    assert response.status_code == 200
    body: Json = response.json()
    offered = set(body["capabilities"])
    assert {"request_item.create", "request_item.update", "binder.read"} <= offered  # binders
    assert {"client_contact.invite", "client_contact.read"} <= offered  # invitations
    # N-01's Files browser (N-01 §4.4, ADR-158) gives a firm admin the metadata read only: the
    # tree and folders, never a file's content (DV-11). Every content action stays out.
    metadata_only = {"evidence.read_metadata"}
    content = {a for a in offered if a.startswith(("evidence.", "comment."))} - metadata_only
    assert not content, offered
    assert "evidence.read" not in offered
    roles = {r["code"]: r["label"] for r in body["roles"]}
    assert "client_service" in roles and roles["client_service"].strip()
    assert body["engagement_id"] == str(engagement)


async def test_t30_capabilities_records_no_authorisation_check(seed: Seeder) -> None:
    firm, _, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    grace = await firm.person("Grace Holloway")
    await firm.member(engagement, grace, "client_service")
    ctx = grace.context()
    with recording_checks() as checked:
        resource = await engagement_resource(ctx.tenant, engagement)
        offered = await allowed_actions(ctx, resource)
        found = await capabilities(ctx, engagement)
    assert "request_item.create" in offered and "request_item.create" in found.capabilities
    assert checked == set()  # "what could I do", never "do it" (ADR-145)


async def test_story_6_1_a_walled_engagements_capabilities_are_404(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "fs_audit", "Ashford")
    lena = await firm.person("Lena Park")
    await firm.member(engagement, lena, "senior")
    client = await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        lena.user_id,
        client,
        partner.user_id,
    )
    response = await http.get(
        "/v1/me/capabilities",
        params={"engagement_id": str(engagement)},
        headers=_auth(idp, lena),
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("roles", "shell"),
    [
        (("owner",), "full"),
        (("k1_recipient",), "k1"),
        (("third_party",), "limited"),
        (("k1_recipient", "owner"), "full"),  # the union of roles (DEC-129)
    ],
)
async def test_ac14_a_client_user_gets_the_portal_shell_and_scopes(
    seed: Seeder,
    http: httpx.AsyncClient,
    idp: FakeIdentityProvider,
    roles: tuple[str, ...],
    shell: str,
) -> None:
    firm, _, engagement = await _staffed(seed, "tax_compliance", "Copperleaf")
    meera = await firm.person("Meera Shah", kind="client")
    for role in roles:
        await seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, $3, 'engagement', $4)",
            firm.tenant,
            meera.user_id,
            role,
            engagement,
        )
    response = await http.get("/v1/me/capabilities", headers=_auth(idp, meera))
    assert response.status_code == 200
    portal = response.json()["portal"]
    assert portal["shell"] == shell
    assert {(s["role"], s["scope_kind"], s["scope_id"]) for s in portal["scopes"]} == {
        (role, "engagement", str(engagement)) for role in roles
    }


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug: GET /v1/me does not carry the Me contract fields (capabilities, roles, flags, "
        "entitlements, office_id, tz, mfa_recent_until); only /v1/me/capabilities does. "
        "F-03 Story 6.2 and SPEC-047 AC-14 (and §4.3 'Extended Me') require both; see #317"
    ),
)
async def test_ac14_me_carries_the_same_fields_as_capabilities(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm = await Firm(seed).make()
    who = await firm.person("Priya Raman")
    response = await http.get("/v1/me", headers=_auth(idp, who))
    assert response.status_code == 200
    assert set(response.json()) >= ME_FIELDS


async def test_ac14_the_engagement_projection_carries_allowed_actions(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "fs_audit", "Northwind")
    archived_client, (entity,) = await firm.client("Bluestem", ["Bluestem"])
    archived = await firm.engagement(
        archived_client, entity, "fs_audit", partner, status="archived"
    )
    await firm.member(archived, partner, "engagement_partner")
    live: Json = (
        await http.get(f"/v1/engagements/{engagement}", headers=_auth(idp, partner))
    ).json()
    done: Json = (
        await http.get(f"/v1/engagements/{archived}", headers=_auth(idp, partner))
    ).json()
    assert "work_item.create" in live["allowed_actions"]
    assert "work_item.create" not in done["allowed_actions"]  # archived is read-only


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bug: record projections carry no read_only_reason (archived, walled, gate_g2, role, "
        "mfa_required, flag_off, entitlement); EngagementOut has allowed_actions only. "
        "F-03 Story 6.2 and SPEC-047 AC-14; see #317"
    ),
)
async def test_ac14_an_archived_engagement_says_why_it_is_read_only(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, _ = await _staffed(seed, "fs_audit", "Northwind")
    client, (entity,) = await firm.client("Bluestem", ["Bluestem"])
    archived = await firm.engagement(client, entity, "fs_audit", partner, status="archived")
    await firm.member(archived, partner, "engagement_partner")
    body: Json = (
        await http.get(f"/v1/engagements/{archived}", headers=_auth(idp, partner))
    ).json()
    assert body.get("read_only_reason") == "archived"


# ================================================================================================
# The list envelope (Story 8.1; §4.6; C1 §3 ListPage[WorkItemRowOut]; F-03-T29)
# ================================================================================================


async def _list(
    http: httpx.AsyncClient, idp: FakeIdentityProvider, who: Who, **params: object
) -> httpx.Response:
    query = {k: str(v) for k, v in params.items() if v is not None}
    return await http.get("/v1/work-items", params=query, headers=_auth(idp, who))


async def _four_kinds(firm: Firm, partner: Who, engagement: uuid.UUID) -> None:
    ctx = partner.context()
    await create_work_item(ctx, engagement, "close", name="Jan", details={"period": "2026-01"})
    await create_work_item(ctx, engagement, "close", name="Feb", details={"period": "2026-02"})
    await create_work_item(
        ctx,
        engagement,
        "notice",
        name="CP2000",
        details={"notice_code": "CP2000", "received_on": date(2026, 9, 1)},
    )
    await create_work_item(
        ctx, engagement, "advisory_project", name="Review", details={"name": "Review"}
    )
    await firm.seed.run(
        "UPDATE work_items SET status = 'archived' WHERE engagement_id = $1 AND kind = 'notice'",
        engagement,
    )


async def test_story_8_1_the_list_is_the_envelope(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "fs_audit", "Copperleaf")
    await _four_kinds(firm, partner, engagement)
    response = await _list(http, idp, partner)
    assert response.status_code == 200
    body: Json = response.json()
    assert {"items", "next_cursor", "total", "total_capped", "counts", "facets"} <= set(body)
    assert body["total"] == 5 and body["total_capped"] is False
    assert body["next_cursor"] is None
    assert body["counts"] == {"active": 4, "archived": 1}
    assert not body["facets"]  # facets only on request
    assert {i["engagement_id"] for i in body["items"]} == {str(engagement)}
    # Newest first: the reverse of the order they were created in (the assurance item first).
    assert [i["name"] for i in body["items"]] == ["Review", "CP2000", "Feb", "Jan", "2026"]


async def test_story_8_1_counts_ignore_the_tile_filter(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "fs_audit", "Copperleaf")
    await _four_kinds(firm, partner, engagement)
    archived: Json = (await _list(http, idp, partner, status="archived")).json()
    assert [i["kind"] for i in archived["items"]] == ["notice"]
    assert archived["total"] == 1
    assert archived["counts"] == {"active": 4, "archived": 1}
    closes: Json = (await _list(http, idp, partner, kind="close")).json()
    assert closes["total"] == 2 and closes["counts"] == {"active": 2}  # other filters apply


def _decoded(cursor: str) -> bytes:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return cursor.encode()


async def test_story_8_1_cursors_are_opaque_and_page_without_overlap(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf Provisions")
    ctx = partner.context()
    for month in range(1, 8):
        period = f"2026-{month:02d}"
        await create_work_item(ctx, engagement, "close", name=period, details={"period": period})
    first: Json = (await _list(http, idp, partner, limit=3)).json()
    cursor = cast(str, first["next_cursor"])
    raw = _decoded(cursor)
    for plain in ("Copperleaf", str(engagement), str(firm.tenant), engagement.hex, "2026-0"):
        assert plain.encode() not in raw and plain not in cursor
    # Not readable JSON. (Ciphertext can hold a `{` byte by chance, so parse rather than scan.)
    with pytest.raises((ValueError, UnicodeDecodeError)):
        json.loads(raw)
    seen = [i["id"] for i in first["items"]]
    while cursor is not None:
        page: Json = (await _list(http, idp, partner, limit=3, cursor=cursor)).json()
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 7


async def test_story_8_1_a_cursor_is_bound_to_its_firm_and_filters(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    _, partner, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    for month in (1, 2, 3):
        period = f"2026-{month:02d}"
        await create_work_item(
            partner.context(), engagement, "close", name=period, details={"period": period}
        )
    cursor = (await _list(http, idp, partner, kind="close", limit=1)).json()["next_cursor"]
    _, outsider, _ = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    other_firm = await _list(http, idp, outsider, kind="close", limit=1, cursor=cursor)
    other_filters = await _list(http, idp, partner, kind="notice", limit=1, cursor=cursor)
    tampered = await _list(http, idp, partner, kind="close", limit=1, cursor=cursor[:-4] + "AAAA")
    for response in (other_firm, other_filters, tampered):
        assert response.status_code == 422
        assert response.json() == {"detail": "cursor_invalid"}  # no facts echo the input


async def test_story_8_1_default_page_is_50_and_the_maximum_is_200(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, engagement = await _staffed(seed, "advisory", "Copperleaf")
    client_id = await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    for n in range(51):
        await seed.run(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'advisory_project', $4, $5)",
            firm.tenant,
            engagement,
            client_id,
            f"Project {n}",
            partner.user_id,
        )
    page: Json = (await _list(http, idp, partner)).json()
    assert len(page["items"]) == 50 and page["next_cursor"] is not None and page["total"] == 51
    assert (await _list(http, idp, partner, limit=200)).status_code == 200
    assert (await _list(http, idp, partner, limit=201)).status_code == 422


async def test_story_6_1_a_walled_engagement_is_left_out_of_the_list_and_its_counts(
    seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider
) -> None:
    firm, partner, granite = await _staffed(seed, "fs_audit", "Granite")
    ashford_client, (ashford_entity,) = await firm.client("Ashford", ["Ashford"])
    ashford = await firm.engagement(ashford_client, ashford_entity, "fs_audit", partner)
    lena = await firm.person("Lena Park")
    for engagement in (granite, ashford):
        await firm.member(engagement, lena, "senior")
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        lena.user_id,
        ashford_client,
        partner.user_id,
    )
    body: Json = (await _list(http, idp, lena)).json()
    assert {i["engagement_id"] for i in body["items"]} == {str(granite)}
    assert body["total"] == 1 and body["counts"] == {"active": 1}
    walled = await _list(http, idp, lena, engagement_id=ashford)
    assert walled.status_code == 200 and walled.json()["items"] == []
    assert walled.json()["total"] == 0


async def test_section_4_6_error_facts_are_identifiers_only(seed: Seeder) -> None:
    _, partner, engagement = await _staffed(seed, "cas_monthly_close", "Copperleaf")
    await create_work_item(
        partner.context(), engagement, "close", name="Jan", details={"period": "2026-01"}
    )
    with pytest.raises(Exception) as refused:
        await create_work_item(
            partner.context(),
            engagement,
            "close",
            name="Copperleaf January (again)",
            details={"period": "2026-01"},
        )
    facts = cast(dict[str, object], getattr(refused.value, "facts", None) or {})
    assert facts, "a 409 names what conflicted"
    for value in facts.values():
        assert _IDENTIFIER.fullmatch(str(value)), value  # never the name or the period text
