"""F-03-T33 against Postgres: independent acceptance tests (ADR-078) for the personas whose facts
live in the database, written from F-03 §3.4-§3.6 (stories 4.3, 5.1, 5.2, 6.1), chapter 03
§4.4-§4.5, ADR-145/146/147 and DEC-127/128/129, not from the code. The unit half is
tests/acceptance/test_f03_personas.py.

- Walled: Lena Park's wall row on Ashford answers 404 through `authorise` and every staff scope
  kind of `visible_scope`, while Granite, where she is also staffed, stays open (INV-3).
- Offshore: `memberships.offshore` refuses `tin.reveal` to the same manager it allows onshore.
- ADM-02: a role template written by `set_policy_override` denies a manager a cell the matrix
  allows; an 'allow' template is refused and nothing is stored (DEC-127).
- Role union: Meera Shah's grants, one written through `grant_client_access`, give the full
  shell, cover her own 1040 and never Ridgeline's return (INV-4); a K-1-only person gets "k1",
  a third party "limited" (DEC-129).
- Client record: a client with only a tax engagement reads non-attest; one with an active audit
  reads attest (DEC-128).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

import asyncpg
import pytest
from sqlalchemy import Uuid, column, select, table, text

import abacus.modules.engagements.api  # registers the client, scope and attest lookups
from abacus.kernel.db import TenantContext, configure_engine, tenant_session
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    grant_client_access,
    portal_scopes,
    visible_scope,
)
from abacus.modules.identity.authz import matrix
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.identity.client_access import scope_covers
from abacus.modules.identity.firm_settings import OverrideRefused, set_policy_override
from abacus.modules.organisations.api import client_record

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.engagements.api

_parse = matrix._rule  # pyright: ignore[reportPrivateUsage]  # the matrix parser, as the codegen uses it
# Chapter 03 §4.4 / DEC-52: `tin.reveal` carries `not_offshore`; it lands with P-07-T04/T10.
TIN_REVEAL_ENTRIES = {
    "engagement_partner": "allow",
    "manager": "allow",
    "not_offshore": "required",
    "mfa_recent": "required",
    "requires": "reason",
}
StaffKind = Literal["engagement", "work_item", "client", "client_entity"]
_TABLES: dict[StaffKind, tuple[str, str, str]] = {
    # list kind: (table, the id a row reports, the column visible_scope filters)
    "engagement": ("engagements", "id", "id"),
    "work_item": ("work_items", "id", "engagement_id"),
    "client": ("clients", "id", "id"),
    "client_entity": ("client_entities", "client_id", "client_id"),
}


class _Client:
    def __init__(self, client: uuid.UUID, entity: uuid.UUID, engagement: uuid.UUID) -> None:
        self.id = client
        self.entity = entity
        self.engagement = engagement
        self.work_item = uuid.uuid4()

    def resource(self, tenant: uuid.UUID) -> Resource:
        return Resource.engagement(tenant, self.engagement, archived=False, client_id=self.id)


class _Firm:
    """A synthetic Brightwater Hale: a partner who creates and leads every engagement."""

    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale')", self.tenant
        )
        self.partner = await self.person(level="partner")
        return self

    async def person(
        self,
        *,
        level: str | None = None,
        offshore: bool = False,
        firm_role: str | None = None,
        client: bool = False,
    ) -> uuid.UUID:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, level, offshore, "
            "firm_role) VALUES ($1, $2, 'active', $3, $4, $5, $6)",
            self.tenant,
            user,
            "client" if client else "staff",
            level,
            offshore,
            firm_role,
        )
        return user

    async def client(
        self, name: str, type_: str = "tax_compliance", *, status: str = "active"
    ) -> _Client:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", self.tenant, name
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            self.tenant,
            client,
            name,
        )
        engagement = await self.seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by, type, status) "
            "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5, $6, $7) RETURNING id",
            self.tenant,
            client,
            entity,
            name,
            self.partner,
            type_,
            status,
        )
        made = _Client(uuid.UUID(str(client)), uuid.UUID(str(entity)), uuid.UUID(str(engagement)))
        made.work_item = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO work_items (tenant_id, engagement_id, client_id, "
                    "client_entity_id, kind, name, created_by) "
                    "VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
                    self.tenant,
                    engagement,
                    client,
                    entity,
                    f"{name} 2025 return",
                    self.partner,
                )
            )
        )
        await self.member(made, self.partner, "engagement_partner")
        return made

    async def member(self, client: _Client, user: uuid.UUID, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            client.engagement,
            user,
            role,
        )

    async def grant(self, user: uuid.UUID, role: str, kind: str, scope: uuid.UUID) -> None:
        await self.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, $3, $4, $5)",
            self.tenant,
            user,
            role,
            kind,
            scope,
        )

    def ctx(self, user: uuid.UUID, firm_role: str | None = None) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(user))
        return AuthContext(tenant, user, uuid.uuid4(), firm_role, datetime.now(UTC))  # type: ignore[arg-type]  # a literal firm role or None


async def _layer(ctx: AuthContext, action: str, resource: Resource, **kw: str) -> str | None:
    try:
        await authorise(ctx, action, resource, **kw)
    except Forbidden as denied:
        return denied.layer
    return None


async def _listed(ctx: AuthContext, kind: StaffKind) -> set[uuid.UUID]:
    name, key, scoped = _TABLES[kind]
    # Columns bound to their table, as a repository's are: the wall subquery correlates on them.
    rows = table(name, *(column(c, Uuid()) for c in dict.fromkeys((key, scoped))))
    query = select(rows.c[key]).where(
        visible_scope(ctx, "engagement.read_metadata", kind, rows.c[scoped])
    )
    async with tenant_session(ctx.tenant) as session:
        return {uuid.UUID(str(v)) for v in (await session.execute(query)).scalars().all()}


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


# --- Walled: Lena Park ✕ Ashford (story 6.1; INV-3) ---------------------------------------------


@pytest.fixture
async def lena(firm: _Firm) -> tuple[AuthContext, _Client, _Client]:
    ashford, granite = await firm.client("Ashford"), await firm.client("Granite")
    lena = await firm.person(level="seasonal")
    await firm.member(ashford, lena, "staff")
    await firm.member(granite, lena, "staff")
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        firm.tenant,
        lena,
        ashford.id,
        firm.partner,
    )
    return firm.ctx(lena), ashford, granite


async def test_walled_lena_gets_404_on_ashford_and_works_on_granite(
    firm: _Firm, lena: tuple[AuthContext, _Client, _Client]
) -> None:
    ctx, ashford, granite = lena
    for action in ("engagement.read_metadata", "work_item.read_metadata", "request_item.read"):
        assert await _layer(ctx, action, ashford.resource(firm.tenant)) == "wall", action  # deny
        assert await _layer(ctx, action, granite.resource(firm.tenant)) is None, action  # allow
    assert await allowed_actions(ctx, ashford.resource(firm.tenant)) == frozenset()


@pytest.mark.parametrize("kind", ["engagement", "work_item", "client", "client_entity"])
async def test_walled_lenas_lists_omit_ashford_and_keep_granite(
    lena: tuple[AuthContext, _Client, _Client], kind: StaffKind
) -> None:
    ctx, ashford, granite = lena
    listed = await _listed(ctx, kind)
    by_kind = {
        "engagement": (ashford.engagement, granite.engagement),
        "work_item": (ashford.work_item, granite.work_item),
        "client": (ashford.id, granite.id),
        "client_entity": (ashford.id, granite.id),
    }
    walled, open_ = by_kind[kind]
    assert walled not in listed
    assert open_ in listed


# --- Offshore: never reveals a TIN (§4.4/§4.5; DEC-52) -------------------------------------------


@pytest.mark.parametrize(("offshore", "layer"), [(True, "condition"), (False, None)])
async def test_offshore_membership_decides_tin_reveal(
    firm: _Firm, monkeypatch: pytest.MonkeyPatch, offshore: bool, layer: str | None
) -> None:
    monkeypatch.setitem(RULES, "tin.reveal", _parse("tin.reveal", TIN_REVEAL_ENTRIES))
    granite = await firm.client("Granite")
    manager = await firm.person(level="manager", offshore=offshore)
    await firm.member(granite, manager, "manager")
    ctx = firm.ctx(manager)
    resource = granite.resource(firm.tenant)
    assert await _layer(ctx, "tin.reveal", resource, reason="Form W-9 check") == layer
    # Offshore narrows only the conditioned action.
    assert await _layer(ctx, "request_item.create", resource) is None


# --- ADM-02 role templates: stricter-only overrides (story 4.3; DEC-127) ------------------------


async def test_a_role_template_narrows_a_manager_and_never_widens(firm: _Firm) -> None:
    granite = await firm.client("Granite")
    manager = await firm.person(level="manager")
    staff = await firm.person(level="staff")
    await firm.member(granite, manager, "manager")
    await firm.member(granite, staff, "staff")
    margaret = firm.ctx(await firm.person(level="partner", firm_role="firm_admin"), "firm_admin")
    resource = granite.resource(firm.tenant)

    assert await _layer(firm.ctx(manager), "request_item.create", resource) is None
    assert await set_policy_override(
        margaret, "request_item.create", "manager", reason="ADM-02: managers don't build binders"
    )
    assert await _layer(firm.ctx(manager), "request_item.create", resource) == "role"
    assert await _layer(firm.ctx(manager), "request_item.update", resource) is None

    # An 'allow' template is refused before anything is stored, and staff stay without the cell.
    with pytest.raises(OverrideRefused):
        await set_policy_override(
            margaret, "request_item.create", "staff", reason="widen", decision="allow"
        )
    stored = await firm.seed.rows(
        "SELECT action, role, decision FROM firm_policy_overrides WHERE tenant_id = $1",
        firm.tenant,
    )
    assert [tuple(r) for r in stored] == [("request_item.create", "manager", "deny")]
    assert await _layer(firm.ctx(staff), "request_item.create", resource) == "role"


async def test_the_database_refuses_an_allow_override(firm: _Firm) -> None:
    """The ceiling holds below the writer too: the table stores only 'deny' (DEC-127)."""
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run(
            "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, "
            "set_by) VALUES ($1, 'request_item.create', 'staff', 'allow', 'widen', $2)",
            firm.tenant,
            firm.partner,
        )


# --- Role union: Meera Shah (story 5.2; INV-4; DEC-129) ------------------------------------------


async def test_meera_shahs_role_union_reaches_her_return_and_never_ridgelines(
    firm: _Firm,
) -> None:
    shah = await firm.client("Shah household")
    ridgeline = await firm.client("Ridgeline Property Partners, LP")
    meera = await firm.person(client=True)
    partner = firm.ctx(firm.partner)
    await grant_client_access(
        partner,
        shah.resource(firm.tenant),
        user_id=meera,
        role="taxpayer",
        scope_kind="work_item",
        scope_id=shah.work_item,
    )
    k1_package = uuid.uuid4()
    await firm.grant(meera, "k1_recipient", "k1_package", k1_package)
    ctx = firm.ctx(meera)

    scopes = await portal_scopes(ctx)
    assert scopes.shell == "full"
    assert {(s.role, s.scope_kind, s.scope_id) for s in scopes.scopes} == {
        ("taxpayer", "work_item", shah.work_item),
        ("k1_recipient", "k1_package", k1_package),
    }
    # Allow: her own 1040. Deny: Ridgeline's return and engagement (404).
    assert await scope_covers(ctx.tenant, meera, shah.engagement, shah.work_item) is True
    assert (
        await scope_covers(ctx.tenant, meera, ridgeline.engagement, ridgeline.work_item) is False
    )
    assert await scope_covers(ctx.tenant, meera, ridgeline.engagement, None) is False
    assert await _layer(ctx, "engagement.read_metadata", ridgeline.resource(firm.tenant)) == (
        "relationship"
    )
    # A portal list shows her return only.
    work_items = table("work_items", column("id", Uuid()))
    query = select(work_items.c.id).where(
        visible_scope(
            ctx,
            "engagement.read_metadata",
            "portal_scope",
            work_items.c.id,
            grant_kind="work_item",
        )
    )
    async with tenant_session(ctx.tenant) as session:
        listed = {uuid.UUID(str(v)) for v in (await session.execute(query)).scalars().all()}
    assert listed == {shah.work_item}
    # INV-5: the grant names the person who granted it.
    by = await firm.seed.value(
        "SELECT e.by_user_id FROM client_access_events e JOIN client_access_grants g "
        "ON g.id = e.grant_id WHERE g.user_id = $1 AND g.role = 'taxpayer' "
        "AND e.event = 'granted'",
        meera,
    )
    assert by == firm.partner


async def test_k1_only_and_third_party_shells(firm: _Firm) -> None:
    shah = await firm.client("Shah household")
    k1_only, third_party = await firm.person(client=True), await firm.person(client=True)
    await firm.grant(k1_only, "k1_recipient", "k1_package", uuid.uuid4())
    await firm.grant(third_party, "third_party", "work_item", shah.work_item)
    assert (await portal_scopes(firm.ctx(k1_only))).shell == "k1"
    assert (await portal_scopes(firm.ctx(third_party))).shell == "limited"
    assert await scope_covers(
        firm.ctx(k1_only).tenant, k1_only, shah.engagement, shah.work_item
    ) is (False)


# --- Client record: is_attest_client (story 5.1; DEC-128) ---------------------------------------


async def test_a_tax_client_reads_non_attest_and_an_audit_client_attest(firm: _Firm) -> None:
    copperleaf = await firm.client("Copperleaf")
    audited = await firm.client("Probe audit client", "fs_audit", status="prospect")
    # As the app does: the derivation trigger reads under the request's tenant (DEC-128).
    async with uow(firm.ctx(firm.partner).tenant) as tx:
        await tx.session.execute(
            text("UPDATE engagements SET status = 'active' WHERE id = :id"),
            {"id": audited.engagement},
        )
        tx.record("engagement.probed", target=Target("engagement", audited.engagement))
    async with tenant_session(firm.ctx(firm.partner).tenant) as session:
        tax_record = await client_record(session, copperleaf.id)
        audit_record = await client_record(session, audited.id)
    assert tax_record is not None and audit_record is not None
    assert tax_record.is_attest_client is False
    assert audit_record.is_attest_client is True
