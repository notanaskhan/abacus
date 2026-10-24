"""P-08-T14 against Postgres (P-08 §1, §5.4; POR-01, POR-02; DEC-213): E0 loaded with the `portal`
slice holds Brightwater Hale's branding row and an active `brightwaterhale.<portal_base_domain>`
host that resolves to it, every portal persona as a client user with a client membership and the
grant P-08 gives them, Dana Kowalski as before, and Sam Ortiz's invitation pending from Sep 2;
Claire Feld's home resolves her household. A second load writes nothing. The figures are typed
from POR-01, POR-02, CLI-04, BND-02 and CLS-03, not from the code.

The load gets its own database: the session's `migrated_db` holds the loader test's E0."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity.api import AuthContext, portal_scopes
from abacus.modules.identity.invitations import preview_invitation
from abacus.modules.portal.branding import branding_for_host
from abacus.modules.portal.home import read_home
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader
from abacus_tools.synthetic.scenarios.brightwater_hale.binders import RETURN_BY_LABEL
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import build

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT
SLICES = ("portal",)
BASE_DOMAIN = "portal-example.test"
HOST = f"brightwaterhale.{BASE_DOMAIN}"
SINK = "sink.brightwaterhale.test"


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


@pytest.fixture
def base_domain(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_PORTAL_BASE_DOMAIN", BASE_DOMAIN)
    settings.cache_clear()
    yield
    monkeypatch.delenv("ABACUS_PORTAL_BASE_DOMAIN")
    settings.cache_clear()


def _user(name: str) -> UUID:
    slug = name.lower().replace(" ", "-")
    return UUID(stable_id(f"user:{slug}"))


def _client_context(user: UUID) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(TENANT, "human", str(user)),
        user_id=user,
        membership_id=uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC),
        client=True,
    )


async def test_e0_with_the_portal_slice_seeds_branding_host_and_personas(
    own_db: Database, base_domain: None
) -> None:
    configure_engine(own_db.app_url)
    seed = Seeder(own_db.superuser_dsn)
    events = build("E0", slices=("audit_core", "binders", "portal")).events

    first = await loader.load(own_db.superuser_dsn, "E0", slices=SLICES, wait=False)
    assert (first.replayed, first.skipped) == (len(events), 0)

    # POR-01a: the branding row, verbatim, no "Secured by" footer.
    branding = await seed.rows(
        "SELECT display_name, address_line, support_contact_name, secured_footer "
        "FROM portal_branding WHERE tenant_id = $1",
        TENANT,
    )
    assert [tuple(r) for r in branding] == [
        (
            "Brightwater Hale",
            "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL",
            "Grace Holloway",
            False,
        )
    ]
    hosts = await seed.rows(
        "SELECT hostname, kind, status FROM portal_domains WHERE tenant_id = $1", TENANT
    )
    assert [tuple(r) for r in hosts] == [(HOST, "default", "active")]
    public = await branding_for_host(f"{HOST}:443")
    assert (public.firm_name, public.address_line, public.secured_footer) == (
        "Brightwater Hale",
        "Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL",
        False,
    )
    assert public.support_contact_name == "Grace Holloway"

    # Every persona: a client user on the sink domain, a client membership, the grant P-08 gives.
    feld = await seed.value(
        "SELECT id FROM clients WHERE tenant_id = $1 AND name = 'Jonah & Claire Feld'", TENANT
    )
    copperleaf = await seed.value(
        "SELECT e.id FROM client_entities e JOIN clients c ON c.id = e.client_id "
        "WHERE e.tenant_id = $1 AND c.name = 'Copperleaf Coffee Roasters, Inc.' "
        "AND e.name = c.name",
        TENANT,
    )
    meera_1040 = UUID(RETURN_BY_LABEL["meera-shah"].id)
    northwind_audit = UUID(stable_id("engagement:A1"))
    grants = await seed.rows(
        "SELECT u.display_name, u.email, m.kind, m.status, g.role, g.scope_kind, g.scope_id, "
        "g.status AS grant_status FROM client_access_grants g "
        "JOIN users u ON u.id = g.user_id "
        "JOIN memberships m ON m.tenant_id = g.tenant_id AND m.user_id = g.user_id "
        "WHERE g.tenant_id = $1 AND u.display_name = ANY($2::text[])",
        TENANT,
        ["Claire Feld", "Tess Moreno", "Ben Ashby", "Meera Shah", "Dana Kowalski"],
    )
    assert {tuple(r) for r in grants} == {
        ("Claire Feld", f"claire.feld@{SINK}", "client", "active", "taxpayer", "client", feld,
         "active"),
        ("Tess Moreno", f"tess.moreno@{SINK}", "client", "active", "owner", "client_entity",
         copperleaf, "active"),
        ("Ben Ashby", f"ben.ashby@{SINK}", "client", "active", "contributor", "client_entity",
         copperleaf, "active"),
        ("Meera Shah", f"meera.shah@{SINK}", "client", "active", "taxpayer", "work_item",
         meera_1040, "active"),
        ("Dana Kowalski", f"dana.kowalski@{SINK}", "client", "active", "owner", "engagement",
         northwind_audit, "active"),
    }  # fmt: skip
    # One user per person (no duplicate rows for anyone the binders slice already names).
    dupes = await seed.value(
        "SELECT count(*) FROM (SELECT display_name FROM users GROUP BY 1 HAVING count(*) > 1) d"
    )
    assert dupes == 0

    # POR-01d: Sam Ortiz's invitation, pending from Wed Sep 2, 2026, Northwind's audit only, with
    # no user or grant before he accepts (P-08-T18).
    invitations = await seed.rows(
        "SELECT i.email, i.role, i.status, i.engagement_id, i.created_at, i.expires_at, "
        "u.display_name "
        "FROM client_invitations i JOIN users u ON u.id = i.invited_by "
        "WHERE i.tenant_id = $1",
        TENANT,
    )
    [sam] = invitations
    assert (sam["email"], sam["role"], sam["status"]) == (
        f"sam.ortiz@{SINK}",
        "client_contributor",
        "pending",
    )
    assert sam["engagement_id"] == northwind_audit
    assert sam["display_name"] == "Grace Holloway"
    assert sam["created_at"].astimezone(UTC).date().isoformat() == "2026-09-02"
    assert (sam["expires_at"] - sam["created_at"]).days == 14
    assert await seed.value("SELECT count(*) FROM users WHERE display_name = 'Sam Ortiz'") == 0
    # P-08-T18: the v2 fields. 9 Northwind requests delegated to Keystone, as a third party's
    # request-scoped grants, through Sam's third-party contact, with terms version 1.
    [v2] = await seed.rows(
        "SELECT i.kind, i.terms_version, i.grant_template::text AS template, c.display_name, "
        "c.organisation_name, c.contact_kind, c.portal_state FROM client_invitations i "
        "JOIN contacts c ON c.id = i.contact_id WHERE i.tenant_id = $1",
        TENANT,
    )
    assert (v2["kind"], v2["terms_version"]) == ("delegate", 1)
    assert (v2["display_name"], v2["organisation_name"], v2["contact_kind"]) == (
        "Sam Ortiz",
        "Keystone Retirement Services",
        "third_party",
    )
    assert v2["portal_state"] == "invited"
    template = json.loads(v2["template"])
    assert (template["role"], template["scope_kind"]) == ("third_party", "request_item")
    assert len(template["scope_ids"]) == 9
    assert (
        await seed.value(
            "SELECT count(DISTINCT engagement_id) FROM request_items WHERE id = ANY($1::uuid[])",
            template["scope_ids"],
        )
        == 1
    )
    assert (
        await seed.value(
            "SELECT engagement_id FROM request_items WHERE id = $1::uuid", template["scope_ids"][0]
        )
        == northwind_audit
    )
    # The preview (POR-01d) once a link is issued: 9 items for the Northwind plan only. Expiry is
    # judged on the database's clock, and Sep 16, 2026 has passed in wall time (DEC-275), so the
    # link is reissued for the check and put back after.
    token = "por01d-" + uuid4().hex + uuid4().hex
    await seed.run(
        "UPDATE client_invitations SET expires_at = now() + interval '14 days' "
        "WHERE tenant_id = $1",
        TENANT,
    )
    await seed.run(
        "INSERT INTO invitation_tokens (token_hash, tenant_id, invitation_id) "
        "SELECT encode(sha256(convert_to($1, 'UTF8')), 'hex'), tenant_id, id "
        "FROM client_invitations WHERE tenant_id = $2",
        token,
        TENANT,
    )
    # The firm's name is read through the identity role: point it at this load's database.
    original = os.environ.get("ABACUS_IDENTITY_DATABASE_URL")
    os.environ["ABACUS_IDENTITY_DATABASE_URL"] = own_db.identity_url
    settings.cache_clear()
    await dispose_engine()
    configure_engine(own_db.app_url)
    try:
        preview = await preview_invitation(HOST, token, "198.51.100.7")
    finally:
        if original is None:
            del os.environ["ABACUS_IDENTITY_DATABASE_URL"]
        else:
            os.environ["ABACUS_IDENTITY_DATABASE_URL"] = original
        settings.cache_clear()
        await dispose_engine()  # later tests configure their own engines
        configure_engine(own_db.app_url)
    assert (preview.access.kind, preview.access.item_count) == ("delegate", 9)
    assert preview.access.scope_label == "Northwind Robotics 401(k) Plan"
    assert (preview.invitee_name, preview.organisation_name) == (
        "Sam Ortiz",
        "Keystone Retirement Services",
    )
    assert preview.firm_name == "Brightwater Hale LLP"
    await seed.run("DELETE FROM invitation_tokens WHERE tenant_id = $1", TENANT)
    await seed.run(
        "UPDATE client_invitations SET expires_at = created_at + interval '14 days' "
        "WHERE tenant_id = $1",
        TENANT,
    )

    # POR-02a: Claire's home resolves her household; she has never dismissed the welcome.
    home = await read_home(_client_context(_user("Claire Feld")), None)
    assert (home.scope.kind, home.scope.id, home.scope.label) == (
        "client",
        feld,
        "Jonah & Claire Feld",
    )
    assert home.scope.role_label == "Taxpayer"
    assert home.binder is not None
    assert (home.binder.done, home.binder.total) == (5, 7)  # BND-02a: the E0 Feld binder
    assert _user("Daniel Reyes") in {m.user_id for m in home.team}
    assert home.first_visit and not home.welcome_dismissed

    # POR-02d: Tess's home is Copperleaf's entity; the close intake has 2 open, one past due.
    tess = await read_home(_client_context(_user("Tess Moreno")), None)
    assert (tess.scope.kind, tess.scope.id) == ("client_entity", copperleaf)
    upload = next(t for t in tess.todos if t.kind == "upload")
    assert (upload.count, upload.state) == (2, "overdue")

    # POR-02e: Meera's scopes are her own 1040 in the full shell (her K-1 grant waits for T-02's
    # package; her home on a work-item scope waits for the role gap TASK-1000 records, DEC-213).
    meera = await portal_scopes(_client_context(_user("Meera Shah")))
    assert meera.shell == "full"
    assert [(g.role, g.scope_kind, g.scope_id) for g in meera.scopes] == [
        ("taxpayer", "work_item", meera_1040)
    ]

    rows = await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT)
    again = await loader.load(own_db.superuser_dsn, "E0", slices=SLICES, wait=False)
    assert (again.replayed, again.skipped) == (0, len(events))
    assert await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", TENANT) == (
        rows
    )
